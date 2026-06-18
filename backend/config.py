from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_URL = f"sqlite+aiosqlite:///{BASE_DIR / 'data' / 'platform.db'}"
YAML_TEMPLATES_DIR = BASE_DIR / "yaml_templates"
SAVES_DIR = BASE_DIR / "saves"
FINETUNE_MODELS_DIR = SAVES_DIR / "finetune_models"
EVAL_RESULTS_DIR = SAVES_DIR / "eval_results"
LLAMAFACTORY_CMD = "llamafactory-cli"
API_PORT_START = 18081
API_PORT_END = 18100
APP_HOST = "0.0.0.0"
APP_PORT = 18080

Path(BASE_DIR / "data").mkdir(parents=True, exist_ok=True)
SAVES_DIR.mkdir(parents=True, exist_ok=True)
FINETUNE_MODELS_DIR.mkdir(parents=True, exist_ok=True)
EVAL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# 日志配置
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "backend.log"
LOG_LEVEL = "DEBUG"
YAML_TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
