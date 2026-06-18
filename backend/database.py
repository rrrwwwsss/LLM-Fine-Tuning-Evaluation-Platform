from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config import DATABASE_URL

# 使用同步 SQLite（不需要 aiosqlite）
SYNC_DATABASE_URL = DATABASE_URL.replace('+aiosqlite', '')
engine = create_engine(SYNC_DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    from models import FinetuneTask, EvalTask, EvalResult, EvalMetric
    Base.metadata.create_all(bind=engine)
    print(f'Database initialized: {engine.url}')
