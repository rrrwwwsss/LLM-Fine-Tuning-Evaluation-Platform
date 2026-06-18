import asyncio
import subprocess
import json
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from database import SessionLocal
from models import FinetuneTask
from services.log_parser import parse_train_log_line
import logging
logger = logging.getLogger("finetune_runner")
from services.process_tracker import register as _reg_proc
from config import BASE_DIR, SAVES_DIR, FINETUNE_MODELS_DIR

class FinetuneRunner:
    _instances: dict = {}

    @classmethod
    def get_instance(cls, task_id: int) -> Optional[dict]:
        return cls._instances.get(task_id)

    @classmethod
    def create_task(cls, name: str, yaml_config: str, yaml_file: str = '') -> FinetuneTask:
        db: Session = SessionLocal()
        try:
            task = FinetuneTask(name=name, yaml_config=yaml_config, yaml_file=yaml_file, status='pending')
            db.add(task)
            db.commit()
            db.refresh(task)
            return task
        finally:
            db.close()

    @classmethod
    def start_task(cls, task_id: int):
        db: Session = SessionLocal()
        try:
            task = db.query(FinetuneTask).filter(FinetuneTask.id == task_id).first()
            if not task:
                raise Exception(f'Task {task_id} not found')
            if task.status == 'running':
                raise Exception('Task already running')

            yaml_path = BASE_DIR / 'data' / f'ft_task_{task_id}.yaml'
            yaml_path.write_text(task.yaml_config, encoding='utf-8')

            output_dir = FINETUNE_MODELS_DIR / task.name
            output_dir.mkdir(parents=True, exist_ok=True)

            log_path = BASE_DIR / 'data' / f'ft_task_{task_id}.log'

            task.status = 'running'
            task.output_dir = str(output_dir)
            task.log_path = str(log_path)
            task.started_at = datetime.now()
            db.commit()

            thread = threading.Thread(target=cls._run_process, args=(task_id, str(yaml_path), str(log_path)), daemon=True)
            thread.start()
        finally:
            db.close()

    @classmethod
    def _run_process(cls, task_id: int, yaml_path: str, log_path: str):
        proc_info: dict = {'running': True}
        cls._instances[task_id] = proc_info
        db: Session = SessionLocal()
        try:
            cmd = ['llamafactory-cli', 'train', yaml_path]
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(BASE_DIR),
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            proc_info['process'] = proc

            loss_history_list = []
            for line_text in proc.stdout:
                line_text = line_text.rstrip()
                with open(log_path, 'a', encoding='utf-8') as f:
                    f.write(line_text + '\n')

                parsed = parse_train_log_line(line_text)
                if parsed:
                    updates = {}
                    if 'current_step' in parsed:
                        updates['current_step'] = parsed['current_step']
                    if 'total_steps' in parsed:
                        updates['total_steps'] = parsed['total_steps']
                    if 'progress' in parsed:
                        updates['progress'] = parsed['progress']
                    if 'current_loss' in parsed:
                        updates['current_loss'] = parsed['current_loss']
                        loss_history_list.append({
                            'step': parsed.get('current_step', 0),
                            'loss': parsed['current_loss'],
                            'epoch': parsed.get('current_epoch', 0)
                        })
                        updates['loss_history'] = json.dumps(loss_history_list)
                    if 'current_epoch' in parsed:
                        updates['current_epoch'] = parsed['current_epoch']
                    if 'total_epochs' in parsed:
                        updates['total_epochs'] = parsed['total_epochs']

                    if updates:
                        db.query(FinetuneTask).filter(FinetuneTask.id == task_id).update(updates)
                        db.commit()

            return_code = proc.poll()
            if return_code and return_code != 0:
                db.query(FinetuneTask).filter(FinetuneTask.id == task_id).update({
                    'status': 'failed', 'finished_at': datetime.now()
                })
            else:
                db.query(FinetuneTask).filter(FinetuneTask.id == task_id).update({
                    'status': 'completed', 'progress': 1.0, 'finished_at': datetime.now()
                })
            db.commit()
        except Exception:
            db.query(FinetuneTask).filter(FinetuneTask.id == task_id).update({
                'status': 'failed', 'finished_at': datetime.now()
            })
            db.commit()
        finally:
            cls._instances.pop(task_id, None)
            db.close()

    @classmethod
    def stop_task(cls, task_id: int):
        proc_info = cls._instances.get(task_id)
        if proc_info and proc_info.get('process'):
            proc_info['process'].terminate()
            import time
            time.sleep(0.5)
            if proc_info['process'].poll() is None:
                proc_info['process'].kill()

        db: Session = SessionLocal()
        try:
            db.query(FinetuneTask).filter(FinetuneTask.id == task_id).update({
                'status': 'stopped', 'finished_at': datetime.now()
            })
            db.commit()
        finally:
            db.close()

    @classmethod
    def delete_task(cls, task_id: int):
        cls.stop_task(task_id)
        db: Session = SessionLocal()
        try:
            task = db.query(FinetuneTask).filter(FinetuneTask.id == task_id).first()
            if task:
                db.delete(task)
                db.commit()
        finally:
            db.close()
