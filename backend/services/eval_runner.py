import json
import csv
import logging
logger = logging.getLogger("eval_runner")
import threading
import requests
import base64
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from database import SessionLocal
from models import EvalTask, EvalResult, EvalMetric, ModelService
from config import BASE_DIR, EVAL_RESULTS_DIR


class EvalRunner:
    _instances: dict = {}

    @classmethod
    def get_instance(cls, task_id: int) -> Optional[dict]:
        return cls._instances.get(task_id)

    @classmethod
    def create_task(cls, name: str, dataset_path: str, model_name_or_path: str,
                    adapter_path: str = "", template: str = "",
                    api_port: int = 0, model_service_id: int = 0) -> EvalTask:
        db = SessionLocal()
        try:
            task = EvalTask(
                name=name, dataset_path=dataset_path,
                model_name_or_path=model_name_or_path,
                api_port=api_port, model_service_id=model_service_id, status="pending"
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            return task
        finally:
            db.close()

    @classmethod
    def extract_result(cls, response):
        import json as _json
        if isinstance(response, dict):
            return response.get("result", "错误")
        if isinstance(response, list) and response:
            response = response[-1]
            if isinstance(response, dict):
                return response.get("result", "错误")
        if isinstance(response, str):
            decoder = _json.JSONDecoder()
            pos = 0
            all_results = []
            while True:
                match_index = response.find("{", pos)
                if match_index == -1:
                    break
                try:
                    result_data, end_index = decoder.raw_decode(response[match_index:])
                    if isinstance(result_data, dict) and "result" in result_data:
                        all_results.append(result_data["result"])
                    pos = match_index + 1
                except _json.JSONDecodeError:
                    pos = match_index + 1
            if all_results:
                return all_results[-1]
        return "错误"

    @classmethod
    def start_task(cls, task_id: int):
        db = SessionLocal()
        try:
            task = db.query(EvalTask).filter(EvalTask.id == task_id).first()
            if not task:
                raise Exception(f"Task {task_id} not found")
            if task.status == "running":
                raise Exception("Task already running")

            # 查找运行中的模型服务
            running_service = db.query(ModelService).filter(
                ModelService.status == "running"
            ).first()
            if not running_service:
                raise Exception("没有找到运行中的模型服务，请先启动模型")

            api_url = running_service.api_url
            if not api_url:
                raise Exception("模型服务 API URL 为空")

            task.status = "running"
            task.api_port = running_service.port
            task.started_at = datetime.now()
            task.log_path = str(BASE_DIR / "data" / f"eval_task_{task_id}.log")
            db.commit()

            thread = threading.Thread(
                target=cls._run_eval,
                args=(task_id, api_url),
                daemon=True
            )
            thread.start()
        finally:
            db.close()

    @classmethod
    def _run_eval(cls, task_id: int, api_url: str):
        proc_info = {"running": True}
        cls._instances[task_id] = proc_info
        db = SessionLocal()
        try:
            task = db.query(EvalTask).filter(EvalTask.id == task_id).first()
            if not task:
                return

            # 查找运行中的模型服务
            db.query(EvalResult).filter(EvalResult.task_id == task_id).delete()
            db.query(EvalMetric).filter(EvalMetric.task_id == task_id).delete()
            db.commit()

            # 创建评测结果 CSV 目录
            safe_name = task.name.replace(" ", "_").replace("/", "_")
            csv_dir = EVAL_RESULTS_DIR / safe_name
            csv_dir.mkdir(parents=True, exist_ok=True)
            results_csv = csv_dir / "results.csv"
            metrics_csv = csv_dir / "metrics.csv"

            # 清理旧CSV文件，避免数据污染
            if results_csv.exists():
                results_csv.unlink()
            if metrics_csv.exists():
                metrics_csv.unlink()

            # 写入CSV表头
            header = ["index", "prompt_text", "image_path", "true_label", "predicted_label", "model_output"]
            with open(str(results_csv), "w", newline="", encoding="utf-8-sig") as cf:
                writer = csv.writer(cf)
                writer.writerow(header)

            df = pd.read_csv(task.dataset_path)
            total = len(df)
            task.total_samples = total
            task.processed_samples = 0
            db.commit()

            # 计算性能指标
            cols = list(df.columns)
            col_lower = [c.lower().replace(" ", "_") for c in cols]

            prompt_col = ""
            label_col = ""
            image_col = ""
            for i, c in enumerate(col_lower):
                if any(k in c for k in ["prompt", "question", "instruction", "query"]):
                    prompt_col = cols[i]
                elif any(k in c for k in ["answer", "result", "output", "response", "label", "model_result", "true_label"]):
                    label_col = cols[i]
                elif any(k in c for k in ["image", "img", "picture", "pic", "photo"]):
                    image_col = cols[i]

            if not prompt_col:
                prompt_col = cols[0]
            if not label_col:
                label_col = cols[1] if len(cols) > 1 else cols[0]

            log_path = Path(str(BASE_DIR / "data" / f"eval_task_{task_id}.log"))
            task.log_path = str(log_path)
            db.commit()
            results_batch = []

            processed = 0
            for idx, row in df.iterrows():
                if not proc_info.get("running", False):
                    break

                prompt_text = str(row.get(prompt_col, ""))
                # 从 model_result 列提取真实标签
                if "model_result" in df.columns:
                    true_label = cls.extract_result(row.get("model_result", ""))
                else:
                    true_label = str(row.get(label_col, ""))
                img_path = str(row.get(image_col, "")) if image_col else ""

                # 调用模型 API
                model_output = ""
                try:
                    messages = []
                    if img_path and Path(img_path).exists():
                        with open(img_path, "rb") as f:
                            b64 = base64.b64encode(f.read()).decode("utf-8")
                        ext = Path(img_path).suffix.lower().lstrip(".")
                        if ext == "jpg":
                            ext = "jpeg"
                        img_data_url = f"data:image/{ext};base64,{b64}"
                        messages.append({
                            "role": "user",
                            "content": [
                                {"type": "image_url", "image_url": {"url": img_data_url}},
                                {"type": "text", "text": prompt_text}
                            ]
                        })
                    else:
                        messages.append({"role": "user", "content": prompt_text or "Hello"})

                    payload = {
                        "model": "default",
                        "messages": messages,
                        "max_tokens": 512,
                        "temperature": 0.1
                    }
                    resp = requests.post(
                        api_url.rstrip("/") + "/v1/chat/completions",
                        json=payload,
                        timeout=120
                    )
                    if resp.status_code == 200:
                        result = resp.json()
                        model_output = result["choices"][0]["message"]["content"]
                    else:
                        model_output = f"[API Error: {resp.status_code}]"

                    with open(str(log_path), "a", encoding="utf-8") as lf:
                        lf.write(f"[{idx}/{total}] {prompt_text[:50]}... -> {model_output[:100]}...\n")

                except Exception as e:
                    model_output = f"[Error: {str(e)[:100]}]"

                predicted_label = cls.extract_result(model_output)
                if predicted_label == "\u9519\u8bef":
                    predicted_label = model_output.strip()[:128]

                result_item = EvalResult(
                    task_id=task_id, sample_index=idx,
                    true_label=true_label, predicted_label=predicted_label,
                    model_output=model_output,
                    prompt_text=prompt_text,
                    image_path=img_path
                )
                db.add(result_item)

                processed += 1
                progress = processed / total if total > 0 else 0
                db.query(EvalTask).filter(EvalTask.id == task_id).update({
                    "processed_samples": processed, "progress": progress
                })
                db.commit()

                # 逐行写入CSV
                with open(str(results_csv), "a", newline="", encoding="utf-8-sig") as cf:
                    writer = csv.writer(cf)
                    writer.writerow([idx, prompt_text, img_path, true_label, predicted_label, model_output])

            # 计算性能指标
            
            from sklearn.metrics import (
                accuracy_score, precision_score, recall_score,
                f1_score, confusion_matrix, classification_report
            )

            all_results = db.query(EvalResult).filter(
                EvalResult.task_id == task_id
            ).all()
            y_true = [r.true_label for r in all_results]
            y_pred = [r.predicted_label for r in all_results]

            try:
                labels = sorted(set(y_true + y_pred))
                acc = accuracy_score(y_true, y_pred)
                prec = precision_score(y_true, y_pred, average="macro", zero_division=0, labels=labels)
                rec = recall_score(y_true, y_pred, average="macro", zero_division=0, labels=labels)
                f1 = f1_score(y_true, y_pred, average="macro", zero_division=0, labels=labels)
                cm = confusion_matrix(y_true, y_pred, labels=labels).tolist()
                cr = classification_report(y_true, y_pred, output_dict=True, zero_division=0, labels=labels)
            except Exception as me:
                import traceback
                logger.error(f"[EvalRunner] task={task_id} metrics ERROR: {traceback.format_exc()}")
                acc = prec = rec = f1 = 0.0
                cm = []
                cr = {}

            # 写入指标 CSV
            with open(str(metrics_csv), "w", newline="", encoding="utf-8-sig") as cf:
                writer = csv.writer(cf)
                writer.writerow(["metric", "value"])
                writer.writerow(["accuracy", acc])
                writer.writerow(["precision", prec])
                writer.writerow(["recall", rec])
                writer.writerow(["f1_score", f1])
                if isinstance(cm, list):
                    writer.writerow(["confusion_matrix", json.dumps(cm, ensure_ascii=False)])

            metric = EvalMetric(
                task_id=task_id, accuracy=acc, precision=prec,
                recall=rec, f1_score=f1,
                confusion_matrix=json.dumps(cm, ensure_ascii=False),
                classification_report=json.dumps(cr, ensure_ascii=False)
            )
            db.add(metric)
            db.query(EvalTask).filter(EvalTask.id == task_id).update({
                "status": "completed", "progress": 1.0,
                "finished_at": datetime.now()
            })
            db.commit()

        except Exception as e:
            import traceback
            error_msg = traceback.format_exc()
            logger.error(f"[EvalRunner] task={task_id} ERROR: {error_msg}")
            try:
                lp = Path(str(BASE_DIR / "data" / f"eval_task_{task_id}.log"))
                with open(str(lp), "a", encoding="utf-8") as lf:
                    lf.write(f"\n[ERROR] {error_msg}\n")
            except:
                pass
            db.query(EvalTask).filter(EvalTask.id == task_id).update({
                "status": "failed", "finished_at": datetime.now()
            })
            db.commit()
        finally:
            cls._instances.pop(task_id, None)
            db.close()

    @classmethod
    def stop_task(cls, task_id: int):
        proc_info = cls._instances.get(task_id)
        if proc_info:
            proc_info["running"] = False
        db = SessionLocal()
        try:
            db.query(EvalTask).filter(EvalTask.id == task_id).update({
                "status": "stopped", "finished_at": datetime.now()
            })
            db.commit()
        finally:
            db.close()

    @classmethod
    def delete_task(cls, task_id: int):
        cls.stop_task(task_id)
        db = SessionLocal()
        try:
            task = db.query(EvalTask).filter(EvalTask.id == task_id).first()
            if task:
                db.delete(task)
                db.commit()
        finally:
            db.close()
