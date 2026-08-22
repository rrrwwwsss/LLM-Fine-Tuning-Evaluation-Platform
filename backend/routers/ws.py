import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from database import SessionLocal
from models import FinetuneTask, EvalTask

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, set[WebSocket]] = {}

    def _get_key(self, channel: str, task_id: int) -> str:
        return f'{channel}:{task_id}'

    async def connect(self, ws: WebSocket, channel: str, task_id: int):
        await ws.accept()
        key = self._get_key(channel, task_id)
        if key not in self._connections:
            self._connections[key] = set()
        self._connections[key].add(ws)
        await self._send_current_state(ws, channel, task_id)

    def disconnect(self, ws: WebSocket, channel: str, task_id: int):
        key = self._get_key(channel, task_id)
        if key in self._connections:
            self._connections[key].discard(ws)
            if not self._connections[key]:
                del self._connections[key]

    async def broadcast(self, channel: str, task_id: int, data: dict):
        key = self._get_key(channel, task_id)
        if key in self._connections:
            stale = set()
            for ws in self._connections[key]:
                try:
                    await ws.send_json(data)
                except Exception:
                    stale.add(ws)
            self._connections[key] -= stale

    async def _send_current_state(self, ws: WebSocket, channel: str, task_id: int):
        db = SessionLocal()
        try:
            if channel == 'finetune':
                task = db.query(FinetuneTask).filter(FinetuneTask.id == task_id).first()
                if task:
                    await ws.send_json({
                        'type': 'state',
                        'status': task.status,
                        'progress': task.progress,
                        'current_epoch': task.current_epoch,
                        'total_epochs': task.total_epochs,
                        'current_step': task.current_step,
                        'total_steps': task.total_steps,
                        'current_loss': task.current_loss,
                        'loss_history': task.loss_history,
                    })
            elif channel == 'eval':
                task = db.query(EvalTask).filter(EvalTask.id == task_id).first()
                if task:
                    await ws.send_json({
                        'type': 'state',
                        'status': task.status,
                        'progress': task.progress,
                        'total_samples': task.total_samples,
                        'processed_samples': task.processed_samples,
                    })
        finally:
            db.close()


manager = ConnectionManager()


@router.websocket('/api/v1/ws/finetune/{task_id}')
async def finetune_ws(ws: WebSocket, task_id: int):
    await manager.connect(ws, 'finetune', task_id)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws, 'finetune', task_id)


@router.websocket('/api/v1/ws/eval/{task_id}')
async def eval_ws(ws: WebSocket, task_id: int):
    await manager.connect(ws, 'eval', task_id)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws, 'eval', task_id)
