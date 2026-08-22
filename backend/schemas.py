from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime

# ====== 微调任务 ======
class FinetuneTaskCreate(BaseModel):
    name: str
    yaml_config: str
    yaml_file: str = ''

class FinetuneTaskUpdate(BaseModel):
    name: Optional[str] = None
    yaml_config: Optional[str] = None
    yaml_file: Optional[str] = ''


class DatasetResponse(BaseModel):
    id: int
    name: str
    original_csv: str
    train_csv: str
    test_csv: str
    train_json: str
    dataset_info_json: str
    train_ratio: float
    status: str
    total_rows: int
    train_rows: int
    test_rows: int
    columns: str
    created_at: Any = None

class DatasetListResponse(BaseModel):
    id: int
    name: str
    status: str
    total_rows: int
    train_rows: int
    test_rows: int
    train_ratio: float
    dataset_info_json: str = ''
    train_json: str = ''
    test_csv: str = ''
    training_stage: str = 'sft'
    created_at: Any = None

class DatasetSplitRequest(BaseModel):
    train_ratio: float = 0.8


class DatasetColumnDefinition(BaseModel):
    name: str
    type: str = 'text'
    role: str = 'other'
    required: bool = False
    default: Any = ''
    source_name: Optional[str] = None


class DatasetCreateRequest(BaseModel):
    name: str
    description: str = ''
    training_stage: str = 'sft'
    columns: list[DatasetColumnDefinition]
    train_ratio: float = 0.8
    image_prefix: str = ''


class DatasetSchemaUpdate(BaseModel):
    description: str = ''
    training_stage: str = 'sft'
    columns: list[DatasetColumnDefinition]
    image_prefix: str = ''


class DatasetRowsCreate(BaseModel):
    rows: list[dict[str, Any]] = Field(default_factory=list)


class DatasetSourceRowUpdate(BaseModel):
    row_index: int
    updates: dict[str, Any]


class DatasetSourceBatchRequest(BaseModel):
    action: str
    scope: str = 'selected'
    row_indices: list[int] = Field(default_factory=list)
    filter_column: str = ''
    filter_mode: str = 'contains'
    filter_value: Any = ''
    assignment_column: str = ''
    assignment_value: Any = ''


class DatasetServerFolderImport(BaseModel):
    folder_path: str
    path_base: str
    common_values: dict[str, Any] = Field(default_factory=dict)


class DatasetServerCsvImport(BaseModel):
    name: str
    csv_path: str
    prefix_path: str = ''


class FinetuneTaskResponse(BaseModel):
    id: int
    name: str
    yaml_config: str
    yaml_file: str
    base_model: str
    output_dir: str
    status: str
    progress: float
    current_epoch: int
    total_epochs: int
    current_step: int
    total_steps: int
    current_loss: float
    loss_history: str
    log_path: str
    pid: int
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

class FinetuneTaskListResponse(BaseModel):
    id: int
    name: str
    base_model: str
    status: str
    progress: float
    training_stage: str = 'sft'
    created_at: datetime

# ====== 评测 ======
class EvalTaskCreate(BaseModel):
    name: str
    dataset_path: str
    model_service_id: int = 0
    model_name_or_path: str = ''
    adapter_path: str = ''
    template: str = ''
    api_port: int = 0

class EvalTaskResponse(BaseModel):
    id: int
    name: str
    dataset_path: str
    model_service_id: int = 0
    model_name_or_path: str = ''
    adapter_path: str = ''
    template: str = ''
    api_port: int = 0
    status: str
    progress: float
    total_samples: int
    processed_samples: int
    api_pid: int
    eval_pid: int
    log_path: str
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

class EvalTaskListResponse(BaseModel):
    id: int
    name: str
    dataset_path: str
    model_name_or_path: str
    model_service_id: int = 0
    status: str
    progress: float
    created_at: datetime

class EvalResultResponse(BaseModel):
    id: int
    task_id: int
    sample_index: int
    true_label: str
    predicted_label: str
    model_output: str
    prompt_text: str
    image_path: str

class EvalMetricResponse(BaseModel):
    id: int
    task_id: int
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    confusion_matrix: str
    classification_report: str

class APIResponse(BaseModel):
    code: int = 0
    message: str = 'success'
    data: Any = None


# ====== 模型服务 ======
class ModelServiceCreate(BaseModel):
    name: str
    model_name_or_path: str
    adapter_path: str = ''
    template: str = ''
    port: int = 0

class ModelServiceResponse(BaseModel):
    id: int
    name: str
    model_name_or_path: str
    adapter_path: str
    template: str
    port: int
    api_url: str
    status: str
    pid: int
    log_path: str
    created_at: Any = None

class ModelChatRequest(BaseModel):
    model_service_id: int
    text: str = ''
    image_path: str = ''

class ModelChatResponse(BaseModel):
    output: str = ''
    error: str = ''
