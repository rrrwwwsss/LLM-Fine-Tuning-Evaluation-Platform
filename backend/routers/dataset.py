import os
import tempfile
from fastapi import APIRouter, Body, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from database import get_db
from models import Dataset
from schemas import DatasetResponse, DatasetListResponse, DatasetSplitRequest, APIResponse
from services.dataset_service import DatasetService
from config import BASE_DIR

router = APIRouter(prefix="/api/v1/dataset", tags=["数据集管理"])



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
            created_at=d.created_at
        ) for d in datasets
    ])


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
