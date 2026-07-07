from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import ModelService
from schemas import (
    ModelServiceCreate, ModelServiceResponse,
    ModelChatRequest, ModelChatResponse, APIResponse
)
from services.model_runner import ModelRunner
from datetime import datetime

router = APIRouter(prefix="/api/v1/model", tags=["模型服务"])


@router.get("/list", response_model=APIResponse)
def list_services():
    services = ModelRunner.list_services()
    return APIResponse(data=[
        ModelServiceResponse(
            id=s.id, name=s.name,
            model_name_or_path=s.model_name_or_path,
            adapter_path=s.adapter_path,
            template=s.template,
            port=s.port, api_url=s.api_url,
            status=s.status, pid=s.pid,
            log_path=s.log_path, created_at=s.created_at
        ) for s in services
    ])


@router.post("/create", response_model=APIResponse)
def create_service(data: ModelServiceCreate):
    try:
        service = ModelRunner.create_service(
            data.name, data.model_name_or_path,
            data.adapter_path, data.template, data.port
        )
        return APIResponse(data=ModelServiceResponse(
            id=service.id, name=service.name,
            model_name_or_path=service.model_name_or_path,
            adapter_path=service.adapter_path,
            template=service.template,
            port=service.port, api_url=service.api_url,
            status=service.status, pid=service.pid,
            log_path=service.log_path, created_at=service.created_at
        ))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{service_id}/start", response_model=APIResponse)
def start_service(service_id: int, max_new_tokens: str = "2048"):
    try:
        ModelRunner.start_service(service_id, max_new_tokens)
        return APIResponse(message="Service starting")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{service_id}/stop", response_model=APIResponse)
def stop_service(service_id: int):
    try:
        ModelRunner.stop_service(service_id)
        return APIResponse(message="Service stopped")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{service_id}", response_model=APIResponse)
def delete_service(service_id: int):
    try:
        ModelRunner.delete_service(service_id)
        return APIResponse(message="Service deleted")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{service_id}", response_model=APIResponse)
def get_service(service_id: int):
    s = ModelRunner.get_service(service_id)
    if not s:
        raise HTTPException(status_code=404, detail="Service not found")
    return APIResponse(data=ModelServiceResponse(
        id=s.id, name=s.name,
        model_name_or_path=s.model_name_or_path,
        adapter_path=s.adapter_path,
        template=s.template,
        port=s.port, api_url=s.api_url,
        status=s.status, pid=s.pid,
        log_path=s.log_path, created_at=s.created_at
    ))


@router.put("/{service_id}/update", response_model=APIResponse)
def update_service(service_id: int, data: dict, db: Session = Depends(get_db)):
    try:
        service = db.query(ModelService).filter(ModelService.id == service_id).first()
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")
        for field in ["name", "model_name_or_path", "adapter_path", "template", "port"]:
            if field in data and data[field] is not None:
                setattr(service, field, data[field])
        db.commit()
        return APIResponse(message="Service updated")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{service_id}/logs", response_model=APIResponse)
def get_service_logs(service_id: int):
    from config import BASE_DIR
    log_path = BASE_DIR / "data" / f"model_{service_id}.log"
    if log_path.exists():
        content = log_path.read_text(encoding="utf-8")
        return APIResponse(data=content)
    return APIResponse(data="")


@router.post("/chat", response_model=APIResponse)
def chat_with_model(data: ModelChatRequest):
    result = ModelRunner.chat(data.model_service_id, data.text, data.image_path)
    return APIResponse(data=ModelChatResponse(
        output=result.get("output", ""),
        error=result.get("error", "")
    ))


@router.get("/running", response_model=APIResponse)
def get_running_service():
    """获取当前系统资源使用情况"""
    services = ModelRunner.list_services()
    for s in services:
        if s.status == "running":
            return APIResponse(data=ModelServiceResponse(
                id=s.id, name=s.name,
                model_name_or_path=s.model_name_or_path,
                adapter_path=s.adapter_path,
                template=s.template,
                port=s.port, api_url=s.api_url,
                status=s.status, pid=s.pid,
                log_path=s.log_path, created_at=s.created_at
            ))
    return APIResponse(data=None)
