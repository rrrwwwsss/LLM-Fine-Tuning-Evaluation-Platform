import datetime
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey
from database import Base

def now():
    return datetime.datetime.now()

class FinetuneTask(Base):
    __tablename__ = 'finetune_tasks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    yaml_config = Column(Text, nullable=False)
    yaml_file = Column(String(255), default='')
    base_model = Column(String(512), default='')
    output_dir = Column(String(512), default='')
    status = Column(String(32), default='pending')
    progress = Column(Float, default=0.0)
    current_epoch = Column(Integer, default=0)
    total_epochs = Column(Integer, default=0)
    current_step = Column(Integer, default=0)
    total_steps = Column(Integer, default=0)
    current_loss = Column(Float, default=0.0)
    loss_history = Column(Text, default='[]')
    log_path = Column(String(512), default='')
    pid = Column(Integer, default=0)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)


class EvalTask(Base):
    __tablename__ = 'eval_tasks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    dataset_path = Column(String(512), nullable=False)
    model_name_or_path = Column(String(512), nullable=False)
    adapter_path = Column(String(512), default='')
    template = Column(String(64), default='')
    api_port = Column(Integer, default=0)
    status = Column(String(32), default='pending')
    progress = Column(Float, default=0.0)
    total_samples = Column(Integer, default=0)
    processed_samples = Column(Integer, default=0)
    api_pid = Column(Integer, default=0)
    model_service_id = Column(Integer, default=0)
    eval_pid = Column(Integer, default=0)
    log_path = Column(String(512), default='')
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)


class EvalResult(Base):
    __tablename__ = 'eval_results'

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey('eval_tasks.id', ondelete='CASCADE'), nullable=False)
    sample_index = Column(Integer, default=0)
    true_label = Column(String(128), default='')
    predicted_label = Column(String(128), default='')
    model_output = Column(Text, default='')
    prompt_text = Column(Text, default='')
    image_path = Column(String(512), default='')
    created_at = Column(DateTime, default=now)



class Dataset(Base):
    __tablename__ = 'datasets'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    original_csv = Column(String(512), default='')       # 原始上传 CSV 路径
    train_csv = Column(String(512), default='')           # 训练集 CSV
    test_csv = Column(String(512), default='')            # 测试集 CSV
    train_json = Column(String(512), default='')          # LLaMA-Factory 格式的 JSON 训练数据
    dataset_info_json = Column(String(512), default='')   # dataset_info.json 路径
    train_ratio = Column(Float, default=0.8)              # 训练集比例
    status = Column(String(32), default='uploaded')       # 已上传/已划分/已转换
    total_rows = Column(Integer, default=0)
    train_rows = Column(Integer, default=0)
    test_rows = Column(Integer, default=0)
    columns = Column(Text, default='[]')                  # CSV 列名
    created_at = Column(DateTime, default=now)

class EvalMetric(Base):
    __tablename__ = 'eval_metrics'

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey('eval_tasks.id', ondelete='CASCADE'), nullable=False)
    accuracy = Column(Float, default=0.0)
    precision = Column(Float, default=0.0)
    recall = Column(Float, default=0.0)
    f1_score = Column(Float, default=0.0)
    confusion_matrix = Column(Text, default='[]')
    classification_report = Column(Text, default='{}')
    created_at = Column(DateTime, default=now)


class ModelService(Base):
    __tablename__ = 'model_services'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), default='')
    model_name_or_path = Column(String(512), default='')
    adapter_path = Column(String(512), default='')
    template = Column(String(64), default='')
    port = Column(Integer, default=0)
    api_url = Column(String(255), default='')
    status = Column(String(32), default='stopped')
    pid = Column(Integer, default=0)
    config_yaml = Column(Text, default='')
    log_path = Column(String(512), default='')
    created_at = Column(DateTime, default=now)
