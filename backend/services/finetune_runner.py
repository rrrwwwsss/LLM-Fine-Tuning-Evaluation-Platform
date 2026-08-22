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

            cls.validate_training_dataset(task.yaml_config)

            yaml_path = BASE_DIR / 'data' / f'ft_task_{task_id}.yaml'
            yaml_path.write_text(task.yaml_config, encoding='utf-8')

            output_dir = FINETUNE_MODELS_DIR / task.name
            output_dir.mkdir(parents=True, exist_ok=True)

            log_path = BASE_DIR / 'data' / f'ft_task_{task_id}.log'

            task.status = 'running'
            task.output_dir = str(output_dir)
            task.log_path = str(log_path)
            task.current_epoch = 0
            task.current_step = 0
            task.current_loss = 0.0
            task.progress = 0.0
            task.loss_history = '[]'
            configured_epochs = cls._yaml_number(task.yaml_config, 'num_train_epochs')
            if configured_epochs is not None:
                task.total_epochs = max(1, int(configured_epochs))
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
            import os
            # Keep metric output flowing while stdout is connected to a pipe.
            ft_env = dict(os.environ, DISABLE_VERSION_CHECK='1', PYTHONUNBUFFERED='1')
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(BASE_DIR),
                text=True,
                encoding='utf-8',
                errors='replace',
                env=ft_env
            )
            proc_info['process'] = proc

            loss_history_list = []
            latest_step = 0
            total_steps = 0
            task = db.query(FinetuneTask).filter(FinetuneTask.id == task_id).first()
            total_epochs = task.total_epochs if task else 0
            for line_text in proc.stdout:
                line_text = line_text.rstrip()
                with open(log_path, 'a', encoding='utf-8') as f:
                    f.write(line_text + '\n')

                parsed = parse_train_log_line(line_text)
                if parsed:
                    updates = {}
                    if 'current_step' in parsed:
                        latest_step = parsed['current_step']
                        updates['current_step'] = latest_step
                    if 'total_steps' in parsed:
                        total_steps = parsed['total_steps']
                        updates['total_steps'] = total_steps
                    if 'progress' in parsed:
                        updates['progress'] = parsed['progress']
                    if 'current_loss' in parsed:
                        updates['current_loss'] = parsed['current_loss']
                        epoch = parsed.get('epoch', 0)
                        loss_step = parsed.get('current_step', latest_step)
                        if epoch and total_steps and total_epochs:
                            loss_step = round(epoch / total_epochs * total_steps)
                        loss_history_list.append({
                            'step': loss_step,
                            'loss': parsed['current_loss'],
                            'epoch': epoch
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
            if not loss_history_list:
                loss_history_list = cls._load_trainer_state(task_id)
                if loss_history_list:
                    last = loss_history_list[-1]
                    db.query(FinetuneTask).filter(FinetuneTask.id == task_id).update({
                        'loss_history': json.dumps(loss_history_list),
                        'current_loss': last['loss'],
                    })
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
            logger.exception("Fine-tuning task %s failed", task_id)
            db.query(FinetuneTask).filter(FinetuneTask.id == task_id).update({
                'status': 'failed', 'finished_at': datetime.now()
            })
            db.commit()
        finally:
            cls._instances.pop(task_id, None)
            db.close()

    @staticmethod
    def _yaml_value(yaml_config: str, key: str) -> Optional[str]:
        import re
        match = re.search(rf'^\s*{re.escape(key)}\s*:\s*([^#\r\n]+)', yaml_config, re.MULTILINE)
        return match.group(1).strip().strip('"\'') if match else None

    @classmethod
    def _yaml_number(cls, yaml_config: str, key: str) -> Optional[float]:
        value = cls._yaml_value(yaml_config, key)
        try:
            return float(value) if value is not None else None
        except ValueError:
            return None

    @classmethod
    def training_stage(cls, yaml_config: str) -> str:
        return (cls._yaml_value(yaml_config, 'stage') or 'sft').lower()

    @classmethod
    def validate_training_dataset(cls, yaml_config: str) -> None:
        stage = cls.training_stage(yaml_config)
        if stage not in {'sft', 'dpo'}:
            return
        dataset_value = cls._yaml_value(yaml_config, 'dataset')
        if not dataset_value:
            raise Exception('Training YAML must specify a dataset')
        explicit_dataset_dir = cls._yaml_value(yaml_config, 'dataset_dir')
        dataset_dir_value = explicit_dataset_dir or './data'
        dataset_dir = Path(dataset_dir_value)
        if not dataset_dir.is_absolute():
            dataset_dir = BASE_DIR / dataset_dir
        info_path = dataset_dir.resolve() / 'dataset_info.json'
        if not info_path.is_file():
            if explicit_dataset_dir:
                raise Exception(f'dataset_info.json not found: {info_path}')
            # Built-in datasets can be resolved from LLaMA-Factory's package.
            return
        try:
            dataset_info = json.loads(info_path.read_text(encoding='utf-8'))
        except Exception as exc:
            raise Exception(f'Invalid dataset_info.json: {exc}') from exc
        dataset_names = [name.strip() for name in dataset_value.split(',') if name.strip()]
        for dataset_name in dataset_names:
            definition = dataset_info.get(dataset_name)
            if not definition:
                raise Exception(f'Dataset {dataset_name} is not registered in dataset_info.json')
            is_preference = definition.get('ranking') is True
            if stage == 'dpo' and not is_preference:
                raise Exception(f'Dataset {dataset_name} is not a DPO preference dataset (ranking=true is required)')
            if stage == 'sft' and is_preference:
                raise Exception(f'Dataset {dataset_name} is a preference dataset; select DPO training instead of SFT')

    @classmethod
    def output_directories(cls, task: FinetuneTask) -> list[Path]:
        candidates: list[Path] = []
        if task.output_dir:
            candidates.append(Path(task.output_dir))
        yaml_output = cls._yaml_value(task.yaml_config or '', 'output_dir')
        if yaml_output:
            path = Path(yaml_output)
            candidates.append(path if path.is_absolute() else BASE_DIR / path)
        unique: list[Path] = []
        for path in candidates:
            resolved = path.resolve()
            if resolved not in unique:
                unique.append(resolved)
        return unique

    @classmethod
    def _load_trainer_state(cls, task_id: int) -> list[dict]:
        state_db: Session = SessionLocal()
        try:
            task = state_db.query(FinetuneTask).filter(FinetuneTask.id == task_id).first()
            if not task:
                return []
            state_files: list[Path] = []
            for output_dir in cls.output_directories(task):
                direct = output_dir / 'trainer_state.json'
                if direct.is_file():
                    state_files.append(direct)
                state_files.extend(output_dir.glob('checkpoint-*/trainer_state.json'))
            if not state_files:
                return []
            state_path = max(state_files, key=lambda path: path.stat().st_mtime)
            state = json.loads(state_path.read_text(encoding='utf-8'))
            return [
                {
                    'step': int(item.get('step', 0)),
                    'loss': float(item['loss']),
                    'epoch': float(item.get('epoch', 0)),
                }
                for item in state.get('log_history', [])
                if item.get('loss') is not None
            ]
        except Exception:
            logger.exception("Could not restore loss history for task %s", task_id)
            return []
        finally:
            state_db.close()

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
