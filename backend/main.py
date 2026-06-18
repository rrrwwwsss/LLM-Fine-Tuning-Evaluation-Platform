import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db
from services.process_tracker import kill_all
from routers import finetune, evaluation, ws, dataset, model
from config import BASE_DIR, APP_PORT, LOG_FILE, LOG_LEVEL

# 配置日志：同时输出到控制台和文件
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.DEBUG),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("backend")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("数据库初始化...")
    init_db()
    logger.info("数据库初始化完成")
    yield
    logger.info("正在清理子进程...")
    kill_all()
    logger.info("后端服务已停止")

app = FastAPI(title='LLM Fine-Tuning & Evaluation Platform', version='1.0.0', lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(finetune.router)
app.include_router(evaluation.router)
app.include_router(ws.router)
app.include_router(dataset.router)
app.include_router(model.router)



@app.get("/api/file")
async def serve_file(path: str = ""):
    import os
    from fastapi.responses import FileResponse
    if not path or not os.path.exists(path):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="File not found")
    media_types = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                   ".gif": "image/gif", ".bmp": "image/bmp", ".webp": "image/webp"}
    ext = os.path.splitext(path)[1].lower()
    media_type = media_types.get(ext, "application/octet-stream")
    return FileResponse(path, media_type=media_type)

@app.get('/api/health')
async def health():
    return {'status': 'ok', 'message': 'LLM Fine-Tuning & Evaluation Platform is running'}


if __name__ == '__main__':
    import uvicorn
    uvicorn.run('main:app', host='0.0.0.0', port=APP_PORT, reload=True,
              log_config=None)  # 使用自定义日志配置
