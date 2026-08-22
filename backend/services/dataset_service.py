import os
import json
import shutil
import re
import uuid
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Dataset
from config import BASE_DIR, SERVER_BROWSE_ROOTS

DATASETS_DIR = BASE_DIR / "data" / "datasets"


class DatasetService:

    ALLOWED_COLUMN_TYPES = {"text", "long_text", "number", "label", "image", "json"}
    ALLOWED_COLUMN_ROLES = {"other", "prompt", "answer", "chosen", "rejected", "image", "label"}
    ALLOWED_TRAINING_STAGES = {"sft", "dpo"}

    @classmethod
    def _dataset_dir(cls, ds: Dataset) -> Path:
        if ds.original_csv:
            return Path(ds.original_csv).parent
        return DATASETS_DIR / f"dataset_{ds.id}"

    @classmethod
    def _schema_path(cls, ds: Dataset) -> Path:
        return cls._dataset_dir(ds) / "schema.json"

    @classmethod
    def _normalize_columns(cls, columns) -> list[dict]:
        normalized = []
        names = set()
        role_counts = {"prompt": 0, "answer": 0, "chosen": 0, "rejected": 0, "image": 0}
        for raw in columns:
            item = raw.model_dump() if hasattr(raw, "model_dump") else dict(raw)
            name = str(item.get("name", "")).strip()
            if not name:
                raise Exception("Column name cannot be empty")
            if name == "_row_id":
                raise Exception("_row_id is reserved by the system")
            if name in names:
                raise Exception(f"Duplicate column name: {name}")
            names.add(name)
            column_type = str(item.get("type", "text"))
            role = str(item.get("role", "other"))
            if column_type not in cls.ALLOWED_COLUMN_TYPES:
                raise Exception(f"Unsupported column type: {column_type}")
            if role not in cls.ALLOWED_COLUMN_ROLES:
                raise Exception(f"Unsupported column role: {role}")
            if role in role_counts:
                role_counts[role] += 1
                if role_counts[role] > 1:
                    raise Exception(f"Only one {role} column is allowed")
            normalized.append({
                "name": name,
                "type": column_type,
                "role": role,
                "required": bool(item.get("required", False)),
                "default": item.get("default", ""),
                "source_name": item.get("source_name") or name,
            })
        if not normalized:
            raise Exception("At least one column is required")
        return normalized

    @classmethod
    def _default_schema(cls, columns: list[str], description: str = "") -> dict:
        mapping = cls._detect_columns(columns)
        definitions = []
        for name in columns:
            role = "other"
            if name == mapping.get("prompt"):
                role = "prompt"
            elif name == mapping.get("answer"):
                role = "answer"
            elif name == mapping.get("image"):
                role = "image"
            definitions.append({
                "name": name,
                "type": "image" if role == "image" else "long_text" if role in {"prompt", "answer"} else "text",
                "role": role,
                "required": role in {"prompt", "answer"},
                "default": "",
                "source_name": name,
            })
        return {"version": 1, "description": description, "training_stage": "sft", "image_prefix": "", "columns": definitions}

    @classmethod
    def _normalize_training_stage(cls, training_stage: str) -> str:
        stage = str(training_stage or "sft").lower().strip()
        if stage not in cls.ALLOWED_TRAINING_STAGES:
            raise Exception(f"Unsupported training stage: {stage}")
        return stage

    @classmethod
    def get_training_stage(cls, ds: Dataset) -> str:
        schema_path = cls._schema_path(ds)
        if not schema_path.is_file():
            return "sft"
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            return cls._normalize_training_stage(schema.get("training_stage", "sft"))
        except Exception:
            return "sft"

    @classmethod
    def get_schema(cls, dataset_id: int) -> dict:
        db: Session = SessionLocal()
        try:
            ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
            if not ds:
                raise Exception("Dataset not found")
            schema_path = cls._schema_path(ds)
            if schema_path.is_file():
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
            else:
                columns = json.loads(ds.columns or "[]")
                schema = cls._default_schema(columns)
            schema["training_stage"] = cls._normalize_training_stage(schema.get("training_stage", "sft"))
            schema["image_prefix"] = str(schema.get("image_prefix", "") or "").replace("\\", "/").rstrip("/")
            schema["columns"] = cls._normalize_columns(schema.get("columns", []))
            return schema
        finally:
            db.close()

    @classmethod
    def _write_schema(cls, ds: Dataset, schema: dict) -> None:
        path = cls._schema_path(ds)
        path.parent.mkdir(parents=True, exist_ok=True)
        clean_columns = []
        for column in schema["columns"]:
            item = dict(column)
            item["source_name"] = item["name"]
            clean_columns.append(item)
        payload = {
            "version": 1,
            "description": schema.get("description", ""),
            "training_stage": cls._normalize_training_stage(schema.get("training_stage", "sft")),
            "image_prefix": str(schema.get("image_prefix", "") or "").replace("\\", "/").rstrip("/"),
            "columns": clean_columns,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _write_csv(df: pd.DataFrame, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        df.to_csv(temp_path, index=False)
        temp_path.replace(path)

    @classmethod
    def create_dataset(cls, name: str, description: str, columns, train_ratio: float = 0.8, training_stage: str = "sft", image_prefix: str = "") -> Dataset:
        if not name.strip():
            raise Exception("Dataset name cannot be empty")
        if not 0 < train_ratio < 1:
            raise Exception("Train ratio must be between 0 and 1")
        normalized = cls._normalize_columns(columns)
        training_stage = cls._normalize_training_stage(training_stage)
        db: Session = SessionLocal()
        ds = Dataset(name=name.strip(), status="uploaded", total_rows=0, train_ratio=train_ratio)
        try:
            db.add(ds)
            db.commit()
            db.refresh(ds)
            dataset_dir = DATASETS_DIR / f"dataset_{ds.id}"
            dataset_dir.mkdir(parents=True, exist_ok=True)
            original_csv = dataset_dir / "original.csv"
            cls._write_csv(pd.DataFrame(columns=[c["name"] for c in normalized]), original_csv)
            ds.original_csv = str(original_csv)
            ds.columns = json.dumps([c["name"] for c in normalized], ensure_ascii=False)
            cls._write_schema(ds, {"description": description, "training_stage": training_stage, "image_prefix": image_prefix, "columns": normalized})
            db.commit()
            db.refresh(ds)
            return ds
        except Exception:
            db.rollback()
            if ds.id:
                shutil.rmtree(DATASETS_DIR / f"dataset_{ds.id}", ignore_errors=True)
                persisted = db.query(Dataset).filter(Dataset.id == ds.id).first()
                if persisted:
                    db.delete(persisted)
                    db.commit()
            raise
        finally:
            db.close()

    @classmethod
    def update_schema(cls, dataset_id: int, description: str, columns, training_stage: str = "sft", image_prefix: str = "") -> dict:
        normalized = cls._normalize_columns(columns)
        training_stage = cls._normalize_training_stage(training_stage)
        db: Session = SessionLocal()
        try:
            ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
            if not ds:
                raise Exception("Dataset not found")
            source_path = Path(ds.original_csv)
            df = pd.read_csv(source_path)
            migrated = pd.DataFrame(index=df.index)
            for column in normalized:
                source_name = column.get("source_name") or column["name"]
                migrated[column["name"]] = df[source_name] if source_name in df.columns else column.get("default", "")
            cls._write_csv(migrated, source_path)
            ds.columns = json.dumps([c["name"] for c in normalized], ensure_ascii=False)
            cls._write_schema(ds, {"description": description, "training_stage": training_stage, "image_prefix": image_prefix, "columns": normalized})
            cls._invalidate_derived(ds)
            db.commit()
            return {"columns": normalized, "description": description, "training_stage": training_stage, "image_prefix": image_prefix}
        finally:
            db.close()

    @classmethod
    def preview_source(
        cls,
        dataset_id: int,
        page: int = 1,
        page_size: int = 50,
        filter_column: str = "",
        filter_mode: str = "contains",
        filter_value: str = "",
    ) -> dict:
        db: Session = SessionLocal()
        try:
            ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
            if not ds or not ds.original_csv:
                raise Exception("Dataset not found")
            df = pd.read_csv(ds.original_csv)
            dataset_total = len(df)
            mask = cls._source_filter_mask(df, filter_column, filter_mode, filter_value)
            filtered = df.loc[mask]
            total = len(filtered)
            offset = max(0, page - 1) * page_size
            rows = filtered.iloc[offset:offset + page_size].copy()
            records = json.loads(rows.to_json(orient="records", force_ascii=False))
            for source_index, record in zip(rows.index.tolist(), records):
                record["_row_index"] = int(source_index)
            return {
                "columns": list(df.columns), "rows": records, "total": total,
                "dataset_total": dataset_total, "page": page, "page_size": page_size,
            }
        finally:
            db.close()

    @staticmethod
    def _source_filter_mask(df: pd.DataFrame, column: str, mode: str, value="") -> pd.Series:
        if not column:
            return pd.Series(True, index=df.index, dtype=bool)
        if column not in df.columns:
            raise Exception(f"Unknown filter column: {column}")
        if mode not in {"contains", "equals", "empty", "not_empty"}:
            raise Exception(f"Unsupported filter mode: {mode}")
        text = df[column].fillna("").astype(str)
        stripped = text.str.strip()
        if mode == "empty":
            return stripped.eq("")
        if mode == "not_empty":
            return stripped.ne("")
        expected = str(value if value is not None else "")
        if mode == "equals":
            return text.eq(expected)
        return text.str.contains(expected, case=False, regex=False, na=False)

    @classmethod
    def batch_source_rows(cls, dataset_id: int, request: dict) -> dict:
        action = str(request.get("action", "")).strip()
        scope = str(request.get("scope", "selected")).strip()
        if action not in {"delete", "assign"}:
            raise Exception("Batch action must be delete or assign")
        if scope not in {"selected", "filtered"}:
            raise Exception("Batch scope must be selected or filtered")
        db: Session = SessionLocal()
        try:
            ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
            if not ds:
                raise Exception("Dataset not found")
            source_path = Path(ds.original_csv)
            df = pd.read_csv(source_path)
            if scope == "selected":
                raw_indices = request.get("row_indices") or []
                indices = sorted({int(index) for index in raw_indices})
                if not indices:
                    raise Exception("Please select at least one row")
                if indices[0] < 0 or indices[-1] >= len(df):
                    raise Exception("Selected row index is out of range")
            else:
                filter_column = str(request.get("filter_column", "")).strip()
                if not filter_column:
                    raise Exception("Please set a filter before operating on filtered rows")
                mask = cls._source_filter_mask(
                    df, filter_column, str(request.get("filter_mode", "contains")),
                    request.get("filter_value", ""),
                )
                indices = [int(index) for index in df.index[mask].tolist()]
                if not indices:
                    raise Exception("No rows match the current filter")

            if action == "delete":
                df = df.drop(index=indices).reset_index(drop=True)
            else:
                schema = cls.get_schema(dataset_id)
                definitions = {column["name"]: column for column in schema["columns"]}
                column_name = str(request.get("assignment_column", "")).strip()
                if column_name not in definitions or column_name not in df.columns:
                    raise Exception("Please select a valid assignment column")
                definition = definitions[column_name]
                value = request.get("assignment_value", "")
                if definition.get("required") and (value is None or str(value).strip() == ""):
                    raise Exception(f"{column_name} is required and cannot be empty")
                if definition["type"] == "number" and value not in (None, ""):
                    try:
                        value = float(value)
                    except (TypeError, ValueError):
                        raise Exception(f"{column_name} must be a number")
                if definition["type"] == "json" and value not in (None, ""):
                    try:
                        json.loads(value if isinstance(value, str) else json.dumps(value))
                    except (TypeError, ValueError, json.JSONDecodeError):
                        raise Exception(f"{column_name} must be valid JSON")
                if definition["type"] != "number":
                    df[column_name] = df[column_name].astype(object)
                df.loc[indices, column_name] = "" if value is None else value

            cls._write_csv(df, source_path)
            ds.total_rows = len(df)
            cls._invalidate_derived(ds)
            db.commit()
            return {"affected": len(indices), "total": len(df), "action": action}
        finally:
            db.close()

    @classmethod
    def resolve_asset(cls, dataset_id: int, relative_path: str) -> Path:
        db: Session = SessionLocal()
        try:
            ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
            if not ds:
                raise Exception("Dataset not found")
            normalized = str(relative_path or "").replace("\\", "/").lstrip("/")
            relative = Path(normalized)
            if not normalized or relative.is_absolute() or ".." in relative.parts:
                raise Exception("Invalid asset path")
            dataset_dir = cls._dataset_dir(ds).resolve()
            asset_path = (dataset_dir / relative).resolve()
            if dataset_dir not in asset_path.parents:
                raise Exception("Asset path is outside the dataset directory")
            if not asset_path.is_file():
                schema_path = cls._schema_path(ds)
                if schema_path.is_file():
                    schema = json.loads(schema_path.read_text(encoding="utf-8"))
                    image_prefix = str(schema.get("image_prefix", "") or "").strip()
                    if image_prefix:
                        server_asset = (Path(image_prefix) / relative).resolve()
                        cls._authorized_server_path(server_asset, require_directory=False)
                        asset_path = server_asset
            if asset_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}:
                raise Exception("Unsupported image format")
            if not asset_path.is_file():
                raise Exception("Image not found")
            return asset_path
        finally:
            db.close()

    @staticmethod
    def _authorized_server_path(path_value, require_directory: bool = True) -> Path:
        candidate = Path(path_value).expanduser().resolve()
        allowed = False
        for configured_root in SERVER_BROWSE_ROOTS:
            root = configured_root.resolve()
            if candidate == root or root in candidate.parents:
                allowed = True
                break
        if not allowed:
            raise Exception("Server path is outside the configured browse roots")
        if require_directory and not candidate.is_dir():
            raise Exception("Server directory not found")
        if not require_directory and not candidate.is_file():
            raise Exception("Server file not found")
        return candidate

    @classmethod
    def list_server_directory(cls, path_value: str = "") -> dict:
        if not path_value:
            unavailable = []
            entries = []
            for configured_root in SERVER_BROWSE_ROOTS:
                root = configured_root.resolve()
                if not root.exists():
                    unavailable.append(f"{root.as_posix()}（目录不存在）")
                    continue
                if not root.is_dir():
                    unavailable.append(f"{root.as_posix()}（不是目录）")
                    continue
                if not os.access(root, os.R_OK | os.X_OK):
                    unavailable.append(f"{root.as_posix()}（启动用户没有读取或进入权限）")
                    continue
                entries.append({
                    "name": root.as_posix(), "path": root.as_posix(),
                    "is_root": True, "kind": "directory",
                })
            if not entries:
                details = "；".join(unavailable) or "没有配置目录"
                raise Exception(f"Linux 目录白名单不可用：{details}。请检查 start.sh 配置并重启后端")
            return {"current": "", "parent": "", "entries": entries, "at_roots": True}
        current = cls._authorized_server_path(path_value)
        root = next(root.resolve() for root in SERVER_BROWSE_ROOTS if current == root.resolve() or root.resolve() in current.parents)
        entries = []
        try:
            for child in current.iterdir():
                if child.is_dir():
                    resolved = child.resolve()
                    if resolved == root or root in resolved.parents:
                        entries.append({"name": child.name, "path": resolved.as_posix(), "is_root": False, "kind": "directory"})
                elif child.is_file() and child.suffix.lower() == ".csv":
                    resolved = child.resolve()
                    if resolved == root or root in resolved.parents:
                        entries.append({"name": child.name, "path": resolved.as_posix(), "is_root": False, "kind": "csv"})
                elif child.is_file() and child.suffix.lower() in {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}:
                    resolved = child.resolve()
                    if resolved == root or root in resolved.parents:
                        entries.append({"name": child.name, "path": resolved.as_posix(), "is_root": False, "kind": "image"})
        except PermissionError as exc:
            raise Exception(f"Cannot read server directory: {exc}") from exc
        entries.sort(key=lambda item: item["name"].lower())
        parent = current.parent.as_posix() if current != root else ""
        return {"current": current.as_posix(), "parent": parent, "entries": entries, "at_roots": False}

    @classmethod
    def _server_image_files(cls, folder: Path) -> list[Path]:
        suffixes = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
        images = []
        for current_dir, directory_names, file_names in os.walk(folder, followlinks=False):
            directory_names.sort()
            for filename in sorted(file_names):
                path = Path(current_dir) / filename
                if path.suffix.lower() in suffixes and path.is_file():
                    cls._authorized_server_path(path, require_directory=False)
                    images.append(path.resolve())
                    if len(images) > 100000:
                        raise Exception("A server folder can contain at most 100000 images")
        return images

    @classmethod
    def inspect_server_image_folder(cls, folder_path: str) -> dict:
        folder = cls._authorized_server_path(folder_path)
        images = cls._server_image_files(folder)
        if not images:
            raise Exception("No supported images found in this server directory")
        root = next(root.resolve() for root in SERVER_BROWSE_ROOTS if folder == root.resolve() or root.resolve() in folder.parents)
        bases = []
        current = root
        bases.append(current)
        for part in folder.relative_to(root).parts:
            current = current / part
            bases.append(current)
        sample = images[0]
        options = [
            {
                "base": base.as_posix(),
                "sample": sample.relative_to(base).as_posix(),
                "label": f"前置路径 {base.as_posix()} → 保存为 {sample.relative_to(base).as_posix()}",
            }
            for base in bases
        ]
        return {"folder": folder.as_posix(), "count": len(images), "sample": sample.as_posix(), "base_options": options}

    @classmethod
    def _validate_rows(cls, rows: list[dict], schema: dict) -> list[dict]:
        columns = schema["columns"]
        names = [c["name"] for c in columns]
        allowed = set(names)
        validated = []
        for row_number, raw in enumerate(rows, start=1):
            extra = set(raw) - allowed
            if extra:
                raise Exception(f"Row {row_number} contains unknown columns: {', '.join(sorted(extra))}")
            item = {}
            for column in columns:
                value = raw.get(column["name"], column.get("default", ""))
                if column.get("required") and (value is None or str(value).strip() == ""):
                    raise Exception(f"Row {row_number}: {column['name']} is required")
                if column["type"] == "number" and value not in (None, ""):
                    try:
                        value = float(value)
                    except (TypeError, ValueError):
                        raise Exception(f"Row {row_number}: {column['name']} must be a number")
                if column["type"] == "json" and value not in (None, ""):
                    try:
                        json.loads(value if isinstance(value, str) else json.dumps(value))
                    except (TypeError, ValueError, json.JSONDecodeError):
                        raise Exception(f"Row {row_number}: {column['name']} must be valid JSON")
                item[column["name"]] = "" if value is None else value
            validated.append(item)
        return validated

    @classmethod
    def append_source_rows(cls, dataset_id: int, rows: list[dict]) -> dict:
        if not rows:
            raise Exception("No rows provided")
        schema = cls.get_schema(dataset_id)
        validated = cls._validate_rows(rows, schema)
        db: Session = SessionLocal()
        try:
            ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
            if not ds:
                raise Exception("Dataset not found")
            path = Path(ds.original_csv)
            df = pd.read_csv(path)
            additions = pd.DataFrame(validated, columns=df.columns)
            df = additions.reset_index(drop=True) if df.empty else pd.concat([df, additions], ignore_index=True)
            cls._write_csv(df, path)
            ds.total_rows = len(df)
            cls._invalidate_derived(ds)
            db.commit()
            return {"added": len(validated), "total": len(df)}
        finally:
            db.close()

    @classmethod
    def update_source_row(cls, dataset_id: int, row_index: int, updates: dict) -> dict:
        schema = cls.get_schema(dataset_id)
        db: Session = SessionLocal()
        try:
            ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
            if not ds:
                raise Exception("Dataset not found")
            path = Path(ds.original_csv)
            df = pd.read_csv(path)
            if row_index < 0 or row_index >= len(df):
                raise Exception("Row index out of range")
            current = df.iloc[row_index].where(pd.notna(df.iloc[row_index]), "").to_dict()
            current.update(updates)
            validated = cls._validate_rows([current], schema)[0]
            type_map = {column["name"]: column["type"] for column in schema["columns"]}
            for key, value in validated.items():
                if type_map.get(key) != "number" and key in df.columns:
                    df[key] = df[key].astype(object)
                df.at[row_index, key] = value
            cls._write_csv(df, path)
            cls._invalidate_derived(ds)
            db.commit()
            return {"row_index": row_index, "updated": list(updates.keys())}
        finally:
            db.close()

    @classmethod
    def delete_source_row(cls, dataset_id: int, row_index: int) -> dict:
        db: Session = SessionLocal()
        try:
            ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
            if not ds:
                raise Exception("Dataset not found")
            path = Path(ds.original_csv)
            df = pd.read_csv(path)
            if row_index < 0 or row_index >= len(df):
                raise Exception("Row index out of range")
            df = df.drop(index=row_index).reset_index(drop=True)
            cls._write_csv(df, path)
            ds.total_rows = len(df)
            cls._invalidate_derived(ds)
            db.commit()
            return {"total": len(df)}
        finally:
            db.close()

    @classmethod
    def save_image(cls, dataset_id: int, filename: str, content: bytes) -> dict:
        cls._validate_image_file(filename, content)
        db: Session = SessionLocal()
        try:
            ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
            if not ds:
                raise Exception("Dataset not found")
            return {"path": cls._save_image_file(ds, filename, content)}
        finally:
            db.close()

    @staticmethod
    def _validate_image_file(filename: str, content: bytes) -> None:
        if len(content) > 20 * 1024 * 1024:
            raise Exception("Image must not exceed 20 MB")
        suffix = Path(filename or "image").suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}:
            raise Exception("Unsupported image format")

    @classmethod
    def _save_image_file(cls, ds: Dataset, filename: str, content: bytes) -> str:
        images_dir = cls._dataset_dir(ds) / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        normalized_name = (filename or "image").replace("\\", "/")
        suffix = Path(normalized_name).suffix.lower()
        safe_stem = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(normalized_name).stem).strip("_") or "image"
        saved_name = f"{uuid.uuid4().hex[:12]}_{safe_stem}{suffix}"
        (images_dir / saved_name).write_bytes(content)
        return f"images/{saved_name}"

    @classmethod
    def _folder_relative_path(cls, filename: str, strip_levels: int = 1) -> str:
        normalized = str(filename or "").replace("\\", "/").strip("/")
        parts = [part for part in normalized.split("/") if part not in ("", ".")]
        if not parts or ".." in parts or re.match(r"^[A-Za-z]:$", parts[0]):
            raise Exception("Invalid image relative path")
        try:
            strip_levels = int(strip_levels)
        except (TypeError, ValueError):
            raise Exception("Invalid image path start level")
        if strip_levels < 0 or strip_levels >= len(parts):
            raise Exception("Image path start level is outside the selected path")
        parts = parts[strip_levels:]
        return Path(*parts).as_posix()

    @classmethod
    def _save_folder_image(cls, ds: Dataset, relative_path: str, content: bytes) -> str:
        """Save a preview copy without changing the folder-relative path or file name."""
        relative_path_obj = Path(relative_path)
        dataset_dir = cls._dataset_dir(ds).resolve()
        target = (dataset_dir / relative_path_obj).resolve()
        if dataset_dir not in target.parents:
            raise Exception("Image path is outside the dataset directory")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return relative_path_obj.as_posix()

    @classmethod
    def import_image_folder(
        cls,
        dataset_id: int,
        files: list[tuple[str, bytes]],
        common_values: Optional[dict] = None,
        path_strip_levels: int = 1,
    ) -> dict:
        if not files:
            raise Exception("No images provided")
        if len(files) > 100:
            raise Exception("Upload at most 100 images per batch")
        for filename, content in files:
            cls._validate_image_file(filename, content)
        schema = cls.get_schema(dataset_id)
        image_column = next((column for column in schema["columns"] if column["role"] == "image"), None)
        if not image_column:
            raise Exception("Please map an Image column before importing a folder")
        common_values = common_values or {}
        definitions = {column["name"]: column for column in schema["columns"]}
        unknown_columns = set(common_values) - set(definitions)
        if unknown_columns:
            raise Exception(f"Unknown common-value columns: {', '.join(sorted(unknown_columns))}")
        if image_column["name"] in common_values:
            raise Exception("The Image column cannot be overwritten by a common value")
        normalized_common_values = {}
        for name, value in common_values.items():
            definition = definitions[name]
            if definition["type"] == "number" and value not in (None, ""):
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    raise Exception(f"Common value for {name} must be a number")
            if definition["type"] == "json" and value not in (None, ""):
                try:
                    json.loads(value if isinstance(value, str) else json.dumps(value))
                except (TypeError, ValueError, json.JSONDecodeError):
                    raise Exception(f"Common value for {name} must be valid JSON")
            normalized_common_values[name] = "" if value is None else value
        db: Session = SessionLocal()
        try:
            ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
            if not ds:
                raise Exception("Dataset not found")
            source_path = Path(ds.original_csv)
            df = pd.read_csv(source_path)
            imported_rows = []
            saved_paths = []
            skipped_paths = []
            existing_paths = {
                str(value).replace("\\", "/").strip("/")
                for value in df[image_column["name"]].dropna().tolist()
                if str(value).strip()
            }
            for filename, content in files:
                relative_path = cls._folder_relative_path(filename, path_strip_levels)
                if relative_path in existing_paths:
                    skipped_paths.append(relative_path)
                    continue
                saved_path = cls._save_folder_image(ds, relative_path, content)
                row = {column["name"]: column.get("default", "") for column in schema["columns"]}
                row.update(normalized_common_values)
                row[image_column["name"]] = saved_path
                imported_rows.append(row)
                saved_paths.append(saved_path)
                existing_paths.add(relative_path)
            if imported_rows:
                additions = pd.DataFrame(imported_rows, columns=df.columns)
                df = additions.reset_index(drop=True) if df.empty else pd.concat([df, additions], ignore_index=True)
                cls._write_csv(df, source_path)
                ds.total_rows = len(df)
                cls._invalidate_derived(ds)
                db.commit()
            return {
                "imported": len(imported_rows), "skipped": len(skipped_paths),
                "total": len(df), "paths": saved_paths, "skipped_paths": skipped_paths,
            }
        finally:
            db.close()

    @classmethod
    def import_server_image_folder(
        cls,
        dataset_id: int,
        folder_path: str,
        path_base: str,
        common_values: Optional[dict] = None,
    ) -> dict:
        folder = cls._authorized_server_path(folder_path)
        base = cls._authorized_server_path(path_base)
        if base != folder and base not in folder.parents:
            raise Exception("The image prefix must be the selected folder or one of its parent directories")
        image_files = cls._server_image_files(folder)
        if not image_files:
            raise Exception("No supported images found in this server directory")
        schema = cls.get_schema(dataset_id)
        image_column = next((column for column in schema["columns"] if column["role"] == "image"), None)
        if not image_column:
            raise Exception("Please map an Image column before importing a server folder")
        common_values = common_values or {}
        definitions = {column["name"]: column for column in schema["columns"]}
        unknown_columns = set(common_values) - set(definitions)
        if unknown_columns:
            raise Exception(f"Unknown common-value columns: {', '.join(sorted(unknown_columns))}")
        if image_column["name"] in common_values:
            raise Exception("The Image column cannot be overwritten by a common value")
        normalized_common_values = {}
        for name, value in common_values.items():
            definition = definitions[name]
            if definition["type"] == "number" and value not in (None, ""):
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    raise Exception(f"Common value for {name} must be a number")
            if definition["type"] == "json" and value not in (None, ""):
                try:
                    json.loads(value if isinstance(value, str) else json.dumps(value))
                except (TypeError, ValueError, json.JSONDecodeError):
                    raise Exception(f"Common value for {name} must be valid JSON")
            normalized_common_values[name] = "" if value is None else value

        db: Session = SessionLocal()
        try:
            ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
            if not ds:
                raise Exception("Dataset not found")
            source_path = Path(ds.original_csv)
            df = pd.read_csv(source_path)
            existing_paths = {
                str(value).replace("\\", "/").strip("/")
                for value in df[image_column["name"]].dropna().tolist()
                if str(value).strip()
            }
            previous_prefix = str(schema.get("image_prefix", "") or "").rstrip("/")
            server_prefix = base.as_posix().rstrip("/")
            if existing_paths and previous_prefix != server_prefix:
                raise Exception(
                    "This dataset already contains images from a different location; "
                    "use a new dataset or keep the same image prefix"
                )
            imported_rows = []
            imported_paths = []
            skipped_paths = []
            for image_file in image_files:
                relative_path = image_file.relative_to(base).as_posix()
                if relative_path in existing_paths:
                    skipped_paths.append(relative_path)
                    continue
                row = {column["name"]: column.get("default", "") for column in schema["columns"]}
                row.update(normalized_common_values)
                row[image_column["name"]] = relative_path
                imported_rows.append(row)
                imported_paths.append(relative_path)
                existing_paths.add(relative_path)
            if imported_rows:
                additions = pd.DataFrame(imported_rows, columns=df.columns)
                df = additions.reset_index(drop=True) if df.empty else pd.concat([df, additions], ignore_index=True)
                cls._write_csv(df, source_path)
                ds.total_rows = len(df)
            schema["image_prefix"] = server_prefix
            cls._write_schema(ds, schema)
            if imported_rows or previous_prefix != server_prefix:
                cls._invalidate_derived(ds)
            db.commit()
            return {
                "imported": len(imported_rows), "skipped": len(skipped_paths),
                "total": len(df), "paths": imported_paths,
                "skipped_paths": skipped_paths, "image_prefix": server_prefix,
            }
        finally:
            db.close()

    @classmethod
    def _invalidate_derived(cls, ds: Dataset) -> None:
        dataset_dir = cls._dataset_dir(ds)
        for filename in ("train.csv", "test.csv", "data.json", "dataset_info.json"):
            path = dataset_dir / filename
            if path.is_file():
                path.unlink()
        ds.train_csv = ""
        ds.test_csv = ""
        ds.train_json = ""
        ds.dataset_info_json = ""
        ds.train_rows = 0
        ds.test_rows = 0
        ds.status = "uploaded"

    @classmethod
    def upload_csv(cls, name: str, csv_path: str, prefix_path: str = "") -> Dataset:
        db: Session = SessionLocal()
        try:
            dataset_dir = DATASETS_DIR / str(int(datetime.now().timestamp()))
            dataset_dir.mkdir(parents=True, exist_ok=True)
            dest_csv = str(dataset_dir / "original.csv")
            shutil.copy2(csv_path, dest_csv)
            df = pd.read_csv(dest_csv, on_bad_lines='skip')
            columns = list(df.columns)

            # 前置路径：拼接到图片列
            if prefix_path:
                prefix_path = prefix_path.replace("\\", "/").rstrip("/")
                img_cols = [c for c in columns if any(k in c.lower().replace(" ", "_") for k in ["image", "img", "picture", "pic", "photo"])]
                for ic in img_cols:
                    df[ic] = df[ic].apply(lambda x: prefix_path + "/" + str(x).replace("\\", "/").lstrip("/") if pd.notna(x) and str(x).strip() else x)

            total = len(df)
            df.to_csv(dest_csv, index=False)
            ds = Dataset(name=name, original_csv=dest_csv, status="uploaded", total_rows=total, columns=json.dumps(columns))
            db.add(ds)
            db.commit()
            db.refresh(ds)
            new_dir = DATASETS_DIR / f"dataset_{ds.id}"
            if dataset_dir.exists():
                dataset_dir.rename(new_dir)
                ds.original_csv = str(new_dir / "original.csv")
                db.commit()
            cls._write_schema(ds, cls._default_schema(columns))
            return ds
        finally:
            db.close()

    @classmethod
    def upload_server_csv(cls, name: str, csv_path: str, prefix_path: str = "") -> Dataset:
        source = cls._authorized_server_path(csv_path, require_directory=False)
        if source.suffix.lower() != ".csv":
            raise Exception("Please select a CSV file from the server")
        return cls.upload_csv(name, str(source), prefix_path)

    @classmethod
    def split_dataset(cls, dataset_id: int, train_ratio: float = 0.8):
        db: Session = SessionLocal()
        try:
            if not 0 < train_ratio < 1:
                raise Exception("Train ratio must be between 0 and 1")
            ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
            if not ds:
                raise Exception("Dataset not found")
            dataset_dir = Path(ds.original_csv).parent
            df = pd.read_csv(ds.original_csv)
            df = df.sample(frac=1, random_state=42).reset_index(drop=True)
            df["_row_id"] = df.index
            split_idx = int(len(df) * train_ratio)
            train_df = df.iloc[:split_idx]
            test_df = df.iloc[split_idx:]
            train_csv = str(dataset_dir / "train.csv")
            test_csv = str(dataset_dir / "test.csv")
            cls._write_csv(train_df, Path(train_csv))
            cls._write_csv(test_df, Path(test_csv))
            ds.train_csv = train_csv
            ds.test_csv = test_csv
            ds.train_ratio = train_ratio
            ds.train_rows = len(train_df)
            ds.test_rows = len(test_df)
            ds.status = "split"
            db.commit()
            cls._do_convert(ds, dataset_dir, db)
            return ds
        finally:
            db.close()

    @classmethod
    def _do_convert(cls, ds: Dataset, dataset_dir: Path, db: Session):
        df = pd.read_csv(ds.train_csv)
        schema_path = cls._schema_path(ds)
        if schema_path.is_file():
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            training_stage = cls._normalize_training_stage(schema.get("training_stage", "sft"))
            image_prefix = str(schema.get("image_prefix", "") or "").strip()
            definitions = cls._normalize_columns(schema.get("columns", []))
            col_map = {
                role: next((c["name"] for c in definitions if c["role"] == role), "")
                for role in ("prompt", "answer", "chosen", "rejected", "image")
            }
        else:
            training_stage = "sft"
            image_prefix = ""
            definitions = []
            col_map = cls._detect_columns(list(df.columns))
            col_map.update({"chosen": "", "rejected": ""})
        required_roles = ("prompt", "chosen", "rejected") if training_stage == "dpo" else ("prompt", "answer")
        missing_roles = [role for role in required_roles if not col_map.get(role)]
        if missing_roles:
            raise Exception(f"Please map the required {training_stage.upper()} columns: {', '.join(missing_roles)}")
        data = []
        for row_index, row in df.iterrows():
            for definition in definitions:
                if definition.get("required") and not cls._cell_text(row.get(definition["name"], "")):
                    raise Exception(f"Row {row_index + 1}: required column {definition['name']} is empty")
            prompt = cls._cell_text(row.get(col_map["prompt"], ""))
            img = cls._cell_text(row.get(col_map["image"], "")) if col_map["image"] else ""
            user_message = {"content": ("<image>" if img else "") + prompt, "role": "user"}
            if training_stage == "dpo":
                chosen = cls._cell_text(row.get(col_map["chosen"], ""))
                rejected = cls._cell_text(row.get(col_map["rejected"], ""))
                if not prompt or not chosen or not rejected:
                    raise Exception(f"DPO row {row_index + 1} has an empty prompt, chosen or rejected value")
                entry = {
                    "messages": [user_message],
                    "chosen": {"content": chosen, "role": "assistant"},
                    "rejected": {"content": rejected, "role": "assistant"},
                }
            else:
                answer = cls._cell_text(row.get(col_map["answer"], ""))
                if not prompt or not answer:
                    raise Exception(f"SFT row {row_index + 1} has an empty prompt or answer value")
                entry = {"messages": [user_message, {"content": answer, "role": "assistant"}]}
            if img:
                entry["images"] = [cls._resolve_data_path(img, dataset_dir, image_prefix)]
            data.append(entry)
        train_json = str(dataset_dir / "data.json")
        with open(train_json, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        dataset_name = f"dataset_{ds.id}"
        info_columns = {"messages": "messages"}
        if training_stage == "dpo":
            info_columns.update({"chosen": "chosen", "rejected": "rejected"})
        if col_map.get("image"):
            info_columns["images"] = "images"
        dataset_entry = {
            "file_name": "data.json",
            "formatting": "sharegpt",
            "columns": info_columns,
            "tags": {"role_tag": "role", "content_tag": "content", "user_tag": "user", "assistant_tag": "assistant"},
        }
        if training_stage == "dpo":
            dataset_entry["ranking"] = True
        dataset_info = {dataset_name: dataset_entry}
        info_json = str(dataset_dir / "dataset_info.json")
        with open(info_json, "w", encoding="utf-8") as f:
            json.dump(dataset_info, f, ensure_ascii=False, indent=2)
        ds.train_json = train_json
        ds.dataset_info_json = info_json
        ds.status = "converted"
        db.commit()

    @staticmethod
    def _cell_text(value) -> str:
        return "" if value is None or pd.isna(value) else str(value)

    @staticmethod
    def _resolve_data_path(value: str, dataset_dir: Path, image_prefix: str = "") -> str:
        normalized = value.replace("\\", "/")
        is_windows_absolute = bool(re.match(r"^[A-Za-z]:/", normalized))
        if normalized.startswith("/") or is_windows_absolute:
            return normalized
        if image_prefix:
            return (Path(image_prefix) / normalized).resolve().as_posix()
        return (dataset_dir / normalized).resolve().as_posix()

    @classmethod
    def convert_to_llamafactory(cls, dataset_id: int):
        db: Session = SessionLocal()
        try:
            ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
            if not ds:
                raise Exception("Dataset not found")
            cls._do_convert(ds, Path(ds.train_csv).parent, db)
            return ds
        finally:
            db.close()

    @classmethod
    def preview_split(cls, dataset_id: int, split: str = "train", page: int = 1, page_size: int = 50):
        db: Session = SessionLocal()
        try:
            ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
            if not ds:
                raise Exception("Dataset not found")
            csv_path = ds.train_csv if split == "train" else ds.test_csv
            if not csv_path or not Path(csv_path).exists():
                raise Exception(f"{split} set not found, split the dataset first")
            df = pd.read_csv(csv_path)
            total = len(df)
            offset = (page - 1) * page_size
            rows = df.iloc[offset:offset + page_size]
            records = json.loads(rows.to_json(orient="records", force_ascii=False))
            for index, record in enumerate(records, start=offset):
                record["_row_index"] = index
            return {"columns": list(df.columns), "total": total, "page": page, "page_size": page_size, "split": split, "rows": records}
        finally:
            db.close()

    @classmethod
    def delete_row(cls, dataset_id: int, split: str, row_index: int):
        db = SessionLocal()
        try:
            ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
            if not ds:
                raise Exception("Dataset not found")
            csv_path = ds.train_csv if split == "train" else ds.test_csv
            if not csv_path or not Path(csv_path).exists():
                raise Exception(f"{split} set not found")
            df = pd.read_csv(csv_path)
            if row_index < 0 or row_index >= len(df):
                raise Exception("Row index out of range")

            # 重新生成 CSV（去掉目标行）
            new_df = df.drop(index=row_index).reset_index(drop=True)
            cls._write_csv(new_df, Path(csv_path))

            # 更新统计信息
            new_rows = len(new_df)
            if split == "train":
                ds.train_rows = new_rows
            else:
                ds.test_rows = new_rows
            ds.total_rows = (ds.train_rows or 0) + (ds.test_rows or 0)
            if split == "train" and ds.status == "converted":
                cls._do_convert(ds, Path(csv_path).parent, db)
            db.commit()
            return {"new_total": new_rows, "split": split}
        finally:
            db.close()

    @classmethod
    def update_row(cls, dataset_id: int, split: str, row_index: int, updates: dict):
        db: Session = SessionLocal()
        try:
            ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
            if not ds:
                raise Exception("Dataset not found")
            csv_path = ds.train_csv if split == "train" else ds.test_csv
            if not csv_path or not Path(csv_path).exists():
                raise Exception(f"{split} set not found")
            df = pd.read_csv(csv_path)
            if row_index < 0 or row_index >= len(df):
                raise Exception("Row index out of range")
            for key, val in updates.items():
                if key in df.columns:
                    df.at[row_index, key] = val
            cls._write_csv(df, Path(csv_path))
            if split == "train" and ds.status == "converted":
                cls._do_convert(ds, Path(csv_path).parent, db)
            return {"row_index": row_index, "updated": list(updates.keys())}
        finally:
            db.close()

    @classmethod
    def _detect_columns(cls, columns):
        col_map = {"prompt": "", "answer": "", "image": ""}
        col_lower = [c.lower().replace(" ", "_") for c in columns]
        for i, c in enumerate(col_lower):
            if any(k in c for k in ["prompt", "question", "instruction", "query"]):
                col_map["prompt"] = columns[i]
            elif any(k in c for k in ["answer", "result", "output", "response", "label", "model_result"]):
                col_map["answer"] = columns[i]
            elif any(k in c for k in ["image", "img", "picture", "pic", "photo"]):
                col_map["image"] = columns[i]
        if not col_map["prompt"]:
            col_map["prompt"] = columns[0] if len(columns) > 0 else ""
        if not col_map["answer"]:
            col_map["answer"] = columns[1] if len(columns) > 1 else columns[0]
        return col_map

    @classmethod
    def list_datasets(cls):
        db: Session = SessionLocal()
        try:
            return db.query(Dataset).order_by(Dataset.created_at.desc()).all()
        finally:
            db.close()

    @classmethod
    def get_dataset(cls, dataset_id: int):
        db: Session = SessionLocal()
        try:
            return db.query(Dataset).filter(Dataset.id == dataset_id).first()
        finally:
            db.close()

    @classmethod
    def get_for_finetune(cls):
        db: Session = SessionLocal()
        try:
            return db.query(Dataset).filter(Dataset.status == "converted").order_by(Dataset.created_at.desc()).all()
        finally:
            db.close()

    @classmethod
    def get_for_eval(cls):
        db: Session = SessionLocal()
        try:
            return db.query(Dataset).filter(Dataset.status.in_(["split", "converted"])).order_by(Dataset.created_at.desc()).all()
        finally:
            db.close()

    @classmethod
    def delete_dataset(cls, dataset_id: int):
        db: Session = SessionLocal()
        try:
            ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
            if ds:
                csv_dir = Path(ds.original_csv).parent.resolve() if ds.original_csv else None
                datasets_root = DATASETS_DIR.resolve()
                if csv_dir and csv_dir != datasets_root and datasets_root in csv_dir.parents and csv_dir.exists():
                    shutil.rmtree(csv_dir)
                db.delete(ds)
                db.commit()
            return ds
        finally:
            db.close()

    @classmethod
    def preview_csv(cls, dataset_id: int, n: int = 5):
        db: Session = SessionLocal()
        try:
            ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
            if not ds or not ds.original_csv:
                raise Exception("Dataset not found")
            df = pd.read_csv(ds.original_csv)
            return {"columns": list(df.columns), "rows": json.loads(df.head(n).to_json(orient="records", force_ascii=False)), "total": len(df)}
        finally:
            db.close()
