import os
import json
import shutil
import pandas as pd
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Dataset
from config import BASE_DIR

DATASETS_DIR = BASE_DIR / "data" / "datasets"


class DatasetService:

    @classmethod
    def upload_csv(cls, name: str, csv_path: str, prefix_path: str = "") -> Dataset:
        db: Session = SessionLocal()
        try:
            dataset_dir = DATASETS_DIR / str(int(datetime.now().timestamp()))
            dataset_dir.mkdir(parents=True, exist_ok=True)
            dest_csv = str(dataset_dir / "original.csv")
            shutil.copy2(csv_path, dest_csv)
            df = pd.read_csv(dest_csv)
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
            return ds
        finally:
            db.close()

    @classmethod
    def split_dataset(cls, dataset_id: int, train_ratio: float = 0.8):
        db: Session = SessionLocal()
        try:
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
            train_df.to_csv(train_csv, index=False)
            test_df.to_csv(test_csv, index=False)
            ds.train_csv = train_csv
            ds.test_csv = test_csv
            ds.train_ratio = train_ratio
            ds.train_rows = len(train_df)
            ds.test_rows = len(test_df)
            ds.status = "split"
            db.commit()
            try:
                cls._do_convert(ds, dataset_dir, db)
            except Exception as e:
                print(f"Auto-convert warning: {e}")
            return ds
        finally:
            db.close()

    @classmethod
    def _do_convert(cls, ds: Dataset, dataset_dir: Path, db: Session):
        df = pd.read_csv(ds.train_csv)
        col_map = cls._detect_columns(list(df.columns))
        data = []
        for _, row in df.iterrows():
            prompt = str(row.get(col_map["prompt"], ""))
            answer = str(row.get(col_map["answer"], ""))
            img = str(row.get(col_map["image"], "")) if col_map["image"] else ""
            messages = [
                {"content": "<image>" + prompt, "role": "user"},
                {"content": answer, "role": "assistant"},
            ]
            entry = {"messages": messages}
            if img:
                entry["images"] = [img]
            data.append(entry)
        train_json = str(dataset_dir / "data.json")
        with open(train_json, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        dataset_name = f"dataset_{ds.id}"
        dataset_info = {
            dataset_name: {
                "file_name": "data.json", "formatting": "sharegpt",
                "columns": {"messages": "messages", "images": "images"},
                "tags": {"role_tag": "role", "content_tag": "content", "user_tag": "user", "assistant_tag": "assistant"},
            }
        }
        info_json = str(dataset_dir / "dataset_info.json")
        with open(info_json, "w", encoding="utf-8") as f:
            json.dump(dataset_info, f, ensure_ascii=False, indent=2)
        ds.train_json = train_json
        ds.dataset_info_json = info_json
        ds.status = "converted"
        db.commit()

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
            return {"columns": list(df.columns), "total": total, "page": page, "page_size": page_size, "split": split, "rows": json.loads(rows.to_json(orient="records", force_ascii=False))}
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
            df.to_csv(csv_path, index=False)
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
                csv_dir = Path(ds.original_csv).parent
                if csv_dir.exists():
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
