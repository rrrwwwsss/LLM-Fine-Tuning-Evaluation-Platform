from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database import get_db
from models import FinetuneTask
from schemas import FinetuneTaskCreate, FinetuneTaskUpdate, FinetuneTaskResponse, FinetuneTaskListResponse, APIResponse
from services.finetune_runner import FinetuneRunner
from config import YAML_TEMPLATES_DIR, BASE_DIR

router = APIRouter(prefix="/api/v1/finetune", tags=["微调任务"])


@router.get("/list", response_model=APIResponse)
def list_tasks(db: Session = Depends(get_db)):
    tasks = db.query(FinetuneTask).order_by(FinetuneTask.created_at.desc()).all()
    return APIResponse(data=[
        FinetuneTaskListResponse(
            id=t.id, name=t.name, base_model=t.base_model,
            status=t.status, progress=t.progress,
            training_stage=FinetuneRunner.training_stage(t.yaml_config),
            created_at=t.created_at
        ) for t in tasks
    ])


@router.post("/create", response_model=APIResponse)
def create_task(data: FinetuneTaskCreate):
    try:
        task = FinetuneRunner.create_task(data.name, data.yaml_config, data.yaml_file)
        return APIResponse(data=FinetuneTaskResponse(
            id=task.id, name=task.name, yaml_config=task.yaml_config,
            yaml_file=task.yaml_file, base_model=task.base_model,
            output_dir=task.output_dir, status=task.status,
            progress=task.progress, current_epoch=task.current_epoch,
            total_epochs=task.total_epochs, current_step=task.current_step,
            total_steps=task.total_steps, current_loss=task.current_loss,
            loss_history=task.loss_history, log_path=task.log_path,
            pid=task.pid, created_at=task.created_at, updated_at=task.updated_at
        ))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{task_id}/yaml", response_model=APIResponse)
def update_task_yaml(task_id: int, data: FinetuneTaskUpdate, db: Session = Depends(get_db)):
    task = db.query(FinetuneTask).filter(FinetuneTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status == "running":
        raise HTTPException(status_code=400, detail="Cannot edit YAML while task is running")
    if data.name is not None:
        task.name = data.name
    if data.yaml_config is not None:
        task.yaml_config = data.yaml_config
    task.yaml_file = data.yaml_file or ""
    db.commit()
    return APIResponse(message="YAML config updated")

@router.get("/yaml-templates", response_model=APIResponse)
def list_yaml_templates():
    files = []
    if YAML_TEMPLATES_DIR.exists():
        for f in sorted(YAML_TEMPLATES_DIR.glob("*.yaml")):
            files.append({"name": f.name, "content": f.read_text(encoding="utf-8")})
    return APIResponse(data=files)


@router.get("/{task_id}", response_model=APIResponse)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(FinetuneTask).filter(FinetuneTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return APIResponse(data=FinetuneTaskResponse(
        id=task.id, name=task.name, yaml_config=task.yaml_config,
        yaml_file=task.yaml_file, base_model=task.base_model,
        output_dir=task.output_dir, status=task.status,
        progress=task.progress, current_epoch=task.current_epoch,
        total_epochs=task.total_epochs, current_step=task.current_step,
        total_steps=task.total_steps, current_loss=task.current_loss,
        loss_history=task.loss_history, log_path=task.log_path,
        pid=task.pid, created_at=task.created_at, updated_at=task.updated_at,
        started_at=task.started_at, finished_at=task.finished_at
    ))


@router.post("/{task_id}/start", response_model=APIResponse)
def start_task(task_id: int):
    try:
        FinetuneRunner.start_task(task_id)
        return APIResponse(message="Task started")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{task_id}/stop", response_model=APIResponse)
def stop_task(task_id: int):
    try:
        FinetuneRunner.stop_task(task_id)
        return APIResponse(message="Task stopped")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{task_id}", response_model=APIResponse)
def delete_task(task_id: int):
    try:
        FinetuneRunner.delete_task(task_id)
        return APIResponse(message="Task deleted")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{task_id}/logs", response_model=APIResponse)
def get_logs(task_id: int):
    log_path = BASE_DIR / "data" / f"ft_task_{task_id}.log"
    if log_path.exists():
        content = log_path.read_text(encoding="utf-8")
        return APIResponse(data=content)
    return APIResponse(data="")


@router.get("/{task_id}/loss-image")
def get_loss_image(task_id: int, db: Session = Depends(get_db)):
    task = db.query(FinetuneTask).filter(FinetuneTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    for output_dir in FinetuneRunner.output_directories(task):
        image_path = output_dir / "training_loss.png"
        if image_path.is_file():
            return FileResponse(image_path, media_type="image/png")
    raise HTTPException(status_code=404, detail="training_loss.png not found")
