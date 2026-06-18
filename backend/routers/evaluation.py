from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import EvalTask, EvalResult, EvalMetric
from schemas import (
    EvalTaskCreate, EvalTaskResponse, EvalTaskListResponse,
    EvalResultResponse, EvalMetricResponse, APIResponse
)
from services.eval_runner import EvalRunner

router = APIRouter(prefix='/api/v1/eval', tags=['评测任务'])


@router.get('/list', response_model=APIResponse)
def list_tasks(db: Session = Depends(get_db)):
    tasks = db.query(EvalTask).order_by(EvalTask.created_at.desc()).all()
    return APIResponse(data=[
        EvalTaskListResponse(
            id=t.id, name=t.name, dataset_path=t.dataset_path,
            model_name_or_path=t.model_name_or_path or '', model_service_id=t.model_service_id or 0, status=t.status,
            progress=t.progress, created_at=t.created_at
        ) for t in tasks
    ])


@router.post('/create', response_model=APIResponse)
def create_task(data: EvalTaskCreate):
    try:
        task = EvalRunner.create_task(
            data.name, data.dataset_path, data.model_name_or_path,
            data.adapter_path, data.template, data.api_port,
            data.model_service_id
        )
        return APIResponse(data=EvalTaskResponse(
            id=task.id, name=task.name, dataset_path=task.dataset_path,
            model_name_or_path=task.model_name_or_path or '',
            adapter_path=task.adapter_path or '', template=task.template or '',
            api_port=task.api_port or 0, model_service_id=task.model_service_id or 0, status=task.status,
            progress=task.progress, total_samples=task.total_samples,
            processed_samples=task.processed_samples,
            api_pid=task.api_pid, eval_pid=task.eval_pid,
            log_path=task.log_path,
            created_at=task.created_at, updated_at=task.updated_at
        ))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get('/{task_id}', response_model=APIResponse)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(EvalTask).filter(EvalTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')
    return APIResponse(data=EvalTaskResponse(
        id=task.id, name=task.name, dataset_path=task.dataset_path,
        model_name_or_path=task.model_name_or_path or '',
        adapter_path=task.adapter_path or '', template=task.template or '',
        api_port=task.api_port or 0, model_service_id=task.model_service_id or 0, status=task.status,
        progress=task.progress, total_samples=task.total_samples,
        processed_samples=task.processed_samples,
        api_pid=task.api_pid, eval_pid=task.eval_pid,
        log_path=task.log_path,
        created_at=task.created_at, updated_at=task.updated_at,
        started_at=task.started_at, finished_at=task.finished_at
    ))


@router.post('/{task_id}/start', response_model=APIResponse)
def start_task(task_id: int):
    try:
        EvalRunner.start_task(task_id)
        return APIResponse(message='Task started')
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/{task_id}/stop', response_model=APIResponse)
def stop_task(task_id: int):
    try:
        EvalRunner.stop_task(task_id)
        return APIResponse(message='Task stopped')
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete('/{task_id}', response_model=APIResponse)
def delete_task(task_id: int):
    try:
        EvalRunner.delete_task(task_id)
        return APIResponse(message='Task deleted')
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get('/{task_id}/results', response_model=APIResponse)
def get_results(task_id: int, page: int = 1, page_size: int = 50, db: Session = Depends(get_db)):
    offset = (page - 1) * page_size
    items = (
        db.query(EvalResult)
        .filter(EvalResult.task_id == task_id)
        .order_by(EvalResult.sample_index)
        .offset(offset).limit(page_size)
        .all()
    )
    total = db.query(EvalResult).filter(EvalResult.task_id == task_id).count()
    return APIResponse(data={
        'total': total,
        'page': page,
        'page_size': page_size,
        'items': [
            EvalResultResponse(
                id=r.id, task_id=r.task_id, sample_index=r.sample_index,
                true_label=r.true_label, predicted_label=r.predicted_label,
                model_output=r.model_output, prompt_text=r.prompt_text,
                image_path=r.image_path
            ) for r in items
        ]
    })


@router.get('/{task_id}/metrics', response_model=APIResponse)
def get_metrics(task_id: int, db: Session = Depends(get_db)):
    metric = (
        db.query(EvalMetric)
        .filter(EvalMetric.task_id == task_id)
        .order_by(EvalMetric.created_at.desc())
        .first()
    )
    if not metric:
        return APIResponse(data=None)
    return APIResponse(data=EvalMetricResponse(
        id=metric.id, task_id=metric.task_id,
        accuracy=metric.accuracy, precision=metric.precision,
        recall=metric.recall, f1_score=metric.f1_score,
        confusion_matrix=metric.confusion_matrix,
        classification_report=metric.classification_report
    ))
