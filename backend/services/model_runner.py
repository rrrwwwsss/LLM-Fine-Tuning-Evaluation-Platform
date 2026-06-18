import subprocess
import os
import threading
import time
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from database import SessionLocal
from models import ModelService
from config import BASE_DIR, API_PORT_START, API_PORT_END
from services.process_tracker import register as _reg_proc


class ModelRunner:
    _instances: dict = {}

    @classmethod
    def get_instance(cls, service_id: int) -> Optional[dict]:
        return cls._instances.get(service_id)

    @classmethod
    def create_service(cls, name: str, model_name_or_path: str,
                       adapter_path: str = "", template: str = "",
                       port: int = 0) -> ModelService:
        db = SessionLocal()
        try:
            if not port:
                port = cls._find_free_port()
            service = ModelService(
                name=name, model_name_or_path=model_name_or_path,
                adapter_path=adapter_path, template=template,
                port=port, status="created"
            )
            db.add(service)
            db.commit()
            db.refresh(service)
            return service
        finally:
            db.close()

    @classmethod
    def start_service(cls, service_id: int):
        db = SessionLocal()
        try:
            service = db.query(ModelService).filter(ModelService.id == service_id).first()
            if not service:
                raise Exception(f"Service {service_id} not found")
            if service.status == "running":
                raise Exception("Service already running")

            log_path = BASE_DIR / "data" / f"model_{service_id}.log"
            api_url = f"http://localhost:{service.port}"

            service.status = "starting"
            service.api_url = api_url
            service.log_path = str(log_path)
            db.commit()

            thread = threading.Thread(
                target=cls._run_api_process,
                args=(service_id, str(log_path), service.port, service.model_name_or_path, service.adapter_path, service.template),
                daemon=True
            )
            thread.start()
        finally:
            db.close()

    @classmethod
    def _run_api_process(cls, service_id: int, log_path: str, port: int, model_name_or_path: str, adapter_path: str, template: str):
        proc_info = {"running": True}
        cls._instances[service_id] = proc_info
        db = SessionLocal()
        try:
            cmd = ["llamafactory-cli", "api", "--model_name_or_path", model_name_or_path, "--template", template, "--finetuning_type", "lora", "--max_new_tokens", "2048"]
            if adapter_path:
                cmd.extend(["--adapter_name_or_path", adapter_path])
            env = dict(os.environ, API_PORT=str(port))

            with open(log_path, "w", encoding="utf-8") as log_f:
                log_f.write(f"Starting: {' '.join(cmd)}\n")

            proc = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            proc_info["process"] = proc
            _reg_proc(proc)
            import threading as _th, time as _time
            def _health():
                _db2 = SessionLocal()
                try:
                    while proc_info.get("running", False):
                        _time.sleep(10)
                        if proc.poll() is not None:
                            break
                    _svc = _db2.query(ModelService).filter(ModelService.id == service_id).first()
                    if _svc and _svc.status in ("running", "starting"):
                        _db2.query(ModelService).filter(ModelService.id == service_id).update({"status": "stopped", "pid": 0})
                        _db2.commit()
                finally:
                    _db2.close()
            _th.Thread(target=_health, daemon=True).start()


            # 读取 API 启动日志
            for line_text in proc.stdout:
                line_text = line_text.rstrip()
                with open(log_path, "a", encoding="utf-8") as log_f:
                    log_f.write(line_text + "\n")

                if "Uvicorn running on" in line_text or "Application startup complete" in line_text:
                    # API 端口被占用则递增
                    db.query(ModelService).filter(ModelService.id == service_id).update({
                        "status": "running", "pid": proc.pid
                    })
                    db.commit()
                    proc_info["ready"] = True

            # 启动模型
            db.query(ModelService).filter(ModelService.id == service_id).update({
                "status": "stopped", "pid": 0
            })
            db.commit()
        except Exception:
            db.query(ModelService).filter(ModelService.id == service_id).update({
                "status": "failed"
            })
            db.commit()
        finally:
            cls._instances.pop(service_id, None)
            db.close()

    @classmethod
    def stop_service(cls, service_id: int):
        proc_info = cls._instances.get(service_id)
        if proc_info and proc_info.get("process"):
            proc_info["process"].terminate()
            time.sleep(0.5)
            if proc_info["process"].poll() is None:
                proc_info["process"].kill()

        db = SessionLocal()
        try:
            db.query(ModelService).filter(ModelService.id == service_id).update({
                "status": "stopped", "pid": 0
            })
            db.commit()
        finally:
            db.close()

    @classmethod
    def delete_service(cls, service_id: int):
        cls.stop_service(service_id)
        db = SessionLocal()
        try:
            service = db.query(ModelService).filter(ModelService.id == service_id).first()
            if service:
                # 生成 YAML 配置文件
                yaml_path = BASE_DIR / "data" / f"model_{service_id}.yaml"
                log_path = BASE_DIR / "data" / f"model_{service_id}.log"
                if yaml_path.exists():
                    yaml_path.unlink()
                if log_path.exists():
                    log_path.unlink()
                db.delete(service)
                db.commit()
        finally:
            db.close()

    @classmethod
    def chat(cls, service_id: int, text: str = "", image_path: str = ""):
        db = SessionLocal()
        try:
            service = db.query(ModelService).filter(ModelService.id == service_id).first()
            if not service or service.status != "running":
                return {"output": "", "error": "Model service is not running"}
            api_url = service.api_url
            if not api_url:
                return {"output": "", "error": "API URL not available"}
        finally:
            db.close()

        # 调用 LLaMA-Factory API（兼容 OpenAI 接口格式）
        try:
            messages = []
            if image_path:
                import base64
                img_path_obj = Path(image_path)
                if img_path_obj.exists():
                    with open(img_path_obj, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode("utf-8")
                    ext = img_path_obj.suffix.lower().lstrip(".")
                    if ext == "jpg":
                        ext = "jpeg"
                    img_url = f"data:image/{ext};base64,{b64}"
                    messages.append({
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": img_url}},
                            {"type": "text", "text": text or "你好"}
                        ]
                    })
                else:
                    messages.append({"role": "user", "content": text or "(image not found)"})
            else:
                messages.append({"role": "user", "content": text or "Hello"})

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
                output = result["choices"][0]["message"]["content"]
                return {"output": output, "error": ""}
            else:
                return {"output": "", "error": f"API error: {resp.status_code} {resp.text[:200]}"}
        except Exception as e:
            return {"output": "", "error": str(e)}

    @classmethod
    def _find_free_port(cls) -> int:
        import socket
        for port in range(API_PORT_START, API_PORT_END + 1):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(("127.0.0.1", port))
            sock.close()
            if result != 0:
                return port
        return API_PORT_START

    @classmethod
    def list_services(cls):
        db = SessionLocal()
        try:
            return db.query(ModelService).order_by(ModelService.created_at.desc()).all()
        finally:
            db.close()

    @classmethod
    def get_service(cls, service_id: int):
        db = SessionLocal()
        try:
            return db.query(ModelService).filter(ModelService.id == service_id).first()
        finally:
            db.close()

# 启动时重置卡住的服务状态
def _reset_stuck_services():
    try:
        from database import SessionLocal
        from models import ModelService
        _db = SessionLocal()
        _db.query(ModelService).filter(ModelService.status.in_(["running", "starting"])).update({"status": "stopped", "pid": 0}, synchronize_session=False)
        _db.commit()
        _db.close()
    except Exception:
        pass
_reset_stuck_services()
