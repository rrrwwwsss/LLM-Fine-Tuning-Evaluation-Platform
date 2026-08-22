import os
import tempfile
from fastapi import APIRouter, Body, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database import get_db
from models import Dataset
from schemas import (
    DatasetResponse, DatasetListResponse, DatasetSplitRequest, APIResponse,
    DatasetCreateRequest, DatasetSchemaUpdate, DatasetRowsCreate,
    DatasetSourceRowUpdate, DatasetSourceBatchRequest, DatasetServerFolderImport,
    DatasetServerCsvImport,
)
from services.dataset_service import DatasetService
from config import BASE_DIR

router = APIRouter(prefix="/api/v1/dataset", tags=["数据集管理"])


def _dataset_response(ds: Dataset) -> DatasetResponse:
    return DatasetResponse(
        id=ds.id, name=ds.name, original_csv=ds.original_csv,
        train_csv=ds.train_csv, test_csv=ds.test_csv,
        train_json=ds.train_json, dataset_info_json=ds.dataset_info_json,
        train_ratio=ds.train_ratio, status=ds.status,
        total_rows=ds.total_rows, train_rows=ds.train_rows,
        test_rows=ds.test_rows, columns=ds.columns,
        created_at=ds.created_at,
    )


@router.post("/create", response_model=APIResponse)
def create_dataset(data: DatasetCreateRequest):
    try:
        ds = DatasetService.create_dataset(
            data.name, data.description, data.columns, data.train_ratio,
            data.training_stage, data.image_prefix,
        )
        return APIResponse(data=_dataset_response(ds), message="Dataset created")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))



@router.get("/for-finetune", response_model=APIResponse)
def list_datasets_for_finetune():
    datasets = DatasetService.get_for_finetune()
    return APIResponse(data=[
        DatasetListResponse(
            id=d.id, name=d.name, status=d.status,
            total_rows=d.total_rows, train_rows=d.train_rows,
            test_rows=d.test_rows, train_ratio=d.train_ratio,
            dataset_info_json=d.dataset_info_json or "",
            train_json=d.train_json or "",
            test_csv=d.test_csv or "",
            training_stage=DatasetService.get_training_stage(d),
            created_at=d.created_at
        ) for d in datasets
    ])


@router.get("/for-eval", response_model=APIResponse)
def list_datasets_for_eval():
    datasets = DatasetService.get_for_eval()
    return APIResponse(data=[
        DatasetListResponse(
            id=d.id, name=d.name, status=d.status,
            total_rows=d.total_rows, train_rows=d.train_rows,
            test_rows=d.test_rows, train_ratio=d.train_ratio,
            dataset_info_json=d.dataset_info_json or "",
            train_json=d.train_json or "",
            test_csv=d.test_csv or "",
            training_stage=DatasetService.get_training_stage(d),
            created_at=d.created_at
        ) for d in datasets
    ])

@router.get("/list", response_model=APIResponse)
def list_datasets():
    datasets = DatasetService.list_datasets()
    return APIResponse(data=[
        DatasetListResponse(
            id=d.id, name=d.name, status=d.status,
            total_rows=d.total_rows, train_rows=d.train_rows,
            test_rows=d.test_rows, train_ratio=d.train_ratio,
            training_stage=DatasetService.get_training_stage(d),
            created_at=d.created_at
        ) for d in datasets
    ])


@router.get("/server-files", response_model=APIResponse)
def browse_server_directories(path: str = ""):
    try:
        return APIResponse(data=DatasetService.list_server_directory(path))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/server-files/inspect", response_model=APIResponse)
def inspect_server_image_directory(path: str):
    try:
        return APIResponse(data=DatasetService.inspect_server_image_folder(path))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{dataset_id}", response_model=APIResponse)
def get_dataset(dataset_id: int):
    ds = DatasetService.get_dataset(dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return APIResponse(data=DatasetResponse(
        id=ds.id, name=ds.name, original_csv=ds.original_csv,
        train_csv=ds.train_csv, test_csv=ds.test_csv,
        train_json=ds.train_json, dataset_info_json=ds.dataset_info_json,
        train_ratio=ds.train_ratio, status=ds.status,
        total_rows=ds.total_rows, train_rows=ds.train_rows,
        test_rows=ds.test_rows, columns=ds.columns,
        created_at=ds.created_at
    ))


@router.get("/{dataset_id}/schema", response_model=APIResponse)
def get_dataset_schema(dataset_id: int):
    try:
        return APIResponse(data=DatasetService.get_schema(dataset_id))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{dataset_id}/schema", response_model=APIResponse)
def update_dataset_schema(dataset_id: int, data: DatasetSchemaUpdate):
    try:
        result = DatasetService.update_schema(
            dataset_id, data.description, data.columns, data.training_stage, data.image_prefix
        )
        return APIResponse(data=result, message="Schema updated")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{dataset_id}/source", response_model=APIResponse)
def preview_dataset_source(
    dataset_id: int,
    page: int = 1,
    page_size: int = 50,
    filter_column: str = "",
    filter_mode: str = "contains",
    filter_value: str = "",
):
    try:
        return APIResponse(data=DatasetService.preview_source(
            dataset_id, page, page_size, filter_column, filter_mode, filter_value
        ))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{dataset_id}/asset")
def get_dataset_asset(dataset_id: int, path: str):
    try:
        asset_path = DatasetService.resolve_asset(dataset_id, path)
        media_types = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
            ".gif": "image/gif", ".bmp": "image/bmp", ".webp": "image/webp",
        }
        return FileResponse(asset_path, media_type=media_types[asset_path.suffix.lower()])
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{dataset_id}/rows", response_model=APIResponse)
def append_dataset_rows(dataset_id: int, data: DatasetRowsCreate):
    try:
        return APIResponse(data=DatasetService.append_source_rows(dataset_id, data.rows), message="Rows added")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{dataset_id}/source-row", response_model=APIResponse)
def update_dataset_source_row(dataset_id: int, data: DatasetSourceRowUpdate):
    try:
        result = DatasetService.update_source_row(dataset_id, data.row_index, data.updates)
        return APIResponse(data=result, message="Row updated")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{dataset_id}/source-row", response_model=APIResponse)
def delete_dataset_source_row(dataset_id: int, row_index: int):
    try:
        return APIResponse(data=DatasetService.delete_source_row(dataset_id, row_index), message="Row deleted")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{dataset_id}/source/batch", response_model=APIResponse)
def batch_update_dataset_source(dataset_id: int, data: DatasetSourceBatchRequest):
    try:
        result = DatasetService.batch_source_rows(dataset_id, data.model_dump())
        return APIResponse(data=result, message="Batch operation completed")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{dataset_id}/images", response_model=APIResponse)
async def upload_dataset_image(dataset_id: int, file: UploadFile = File(...)):
    try:
        content = await file.read()
        return APIResponse(data=DatasetService.save_image(dataset_id, file.filename or "image", content), message="Image uploaded")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{dataset_id}/images/bulk", response_model=APIResponse)
async def import_dataset_image_folder(
    dataset_id: int,
    files: list[UploadFile] = File(...),
    common_values: str = Form("{}"),
    relative_paths: str = Form("[]"),
    path_strip_levels: int = Form(1),
):
    try:
        import json
        parsed_common_values = json.loads(common_values)
        if not isinstance(parsed_common_values, dict):
            raise Exception("common_values must be a JSON object")
        parsed_relative_paths = json.loads(relative_paths)
        if not isinstance(parsed_relative_paths, list):
            raise Exception("relative_paths must be a JSON array")
        if parsed_relative_paths and len(parsed_relative_paths) != len(files):
            raise Exception("relative_paths must match the uploaded files")
        payload = [
            (
                str(parsed_relative_paths[index]) if parsed_relative_paths else (file.filename or "image"),
                await file.read(),
            )
            for index, file in enumerate(files)
        ]
        result = DatasetService.import_image_folder(
            dataset_id, payload, parsed_common_values, path_strip_levels
        )
        return APIResponse(data=result, message="Images imported and rows created")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{dataset_id}/images/server-folder", response_model=APIResponse)
def import_server_image_folder(dataset_id: int, data: DatasetServerFolderImport):
    try:
        result = DatasetService.import_server_image_folder(
            dataset_id, data.folder_path, data.path_base, data.common_values
        )
        return APIResponse(data=result, message="Server images imported and rows created")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))



@router.get("/{dataset_id}/preview-split", response_model=APIResponse)
def preview_split(dataset_id: int, split: str = "train", page: int = 1, page_size: int = 50):
    try:
        result = DatasetService.preview_split(dataset_id, split, page, page_size)
        return APIResponse(data=result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{dataset_id}/row", response_model=APIResponse)
def update_row(dataset_id: int, split: str = Body("train"), row_index: int = Body(...), updates: dict = Body(...)):
    try:
        import logging
        logger = logging.getLogger("dataset_router")
        logger.info(f"update_row: dataset_id={dataset_id}, split={split}, row_index={row_index}, updates={str(updates)[:200]}")
        result = DatasetService.update_row(dataset_id, split, row_index, updates)
        return APIResponse(data=result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{dataset_id}/row", response_model=APIResponse)
def delete_row(dataset_id: int, split: str = "train", row_index: int = 0):
    try:
        result = DatasetService.delete_row(dataset_id, split, row_index)
        return APIResponse(data=result, message="Row deleted")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{dataset_id}/preview", response_model=APIResponse)
def preview_dataset(dataset_id: int, n: int = 5):
    try:
        result = DatasetService.preview_csv(dataset_id, n)
        return APIResponse(data=result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/upload", response_model=APIResponse)
async def upload_dataset(name: str = Form(...), file: UploadFile = File(...), prefix_path: str = Form("")):
    try:
        # 保存上传文件到临时路径
        suffix = os.path.splitext(file.filename)[1] or ".csv"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        content = await file.read()
        tmp.write(content)
        tmp.close()

        ds = DatasetService.upload_csv(name, tmp.name, prefix_path)
        os.unlink(tmp.name)  # 清理临时文件

        return APIResponse(data=DatasetResponse(
            id=ds.id, name=ds.name, original_csv=ds.original_csv,
            train_csv=ds.train_csv, test_csv=ds.test_csv,
            train_json=ds.train_json, dataset_info_json=ds.dataset_info_json,
            train_ratio=ds.train_ratio, status=ds.status,
            total_rows=ds.total_rows, train_rows=ds.train_rows,
            test_rows=ds.test_rows, columns=ds.columns,
            created_at=ds.created_at
        ))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/upload-server", response_model=APIResponse)
def upload_server_dataset(data: DatasetServerCsvImport):
    try:
        ds = DatasetService.upload_server_csv(data.name, data.csv_path, data.prefix_path)
        return APIResponse(data=_dataset_response(ds), message="Server CSV imported")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{dataset_id}/split", response_model=APIResponse)
def split_dataset(dataset_id: int, data: DatasetSplitRequest = DatasetSplitRequest()):
    try:
        ds = DatasetService.split_dataset(dataset_id, data.train_ratio)
        return APIResponse(data=DatasetResponse(
            id=ds.id, name=ds.name, original_csv=ds.original_csv,
            train_csv=ds.train_csv, test_csv=ds.test_csv,
            train_json=ds.train_json, dataset_info_json=ds.dataset_info_json,
            train_ratio=ds.train_ratio, status=ds.status,
            total_rows=ds.total_rows, train_rows=ds.train_rows,
            test_rows=ds.test_rows, columns=ds.columns,
            created_at=ds.created_at
        ))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{dataset_id}/convert", response_model=APIResponse)
def convert_dataset(dataset_id: int):
    try:
        ds = DatasetService.convert_to_llamafactory(dataset_id)
        return APIResponse(data=DatasetResponse(
            id=ds.id, name=ds.name, original_csv=ds.original_csv,
            train_csv=ds.train_csv, test_csv=ds.test_csv,
            train_json=ds.train_json, dataset_info_json=ds.dataset_info_json,
            train_ratio=ds.train_ratio, status=ds.status,
            total_rows=ds.total_rows, train_rows=ds.train_rows,
            test_rows=ds.test_rows, columns=ds.columns,
            created_at=ds.created_at
        ))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{dataset_id}", response_model=APIResponse)
def delete_dataset(dataset_id: int):
    ds = DatasetService.delete_dataset(dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return APIResponse(message="Dataset deleted")
