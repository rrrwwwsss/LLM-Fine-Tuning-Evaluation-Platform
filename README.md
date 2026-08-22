# LLM Fine-Tuning & Evaluation Platform

大模型微调 + 自动评测平台，基于 **Vue3 + FastAPI + SQLite** 架构，支持使用 LLaMA-Factory 进行模型微调，并提供基于 sklearn 的自动评测能力。

---

## 项目结构

```
├── backend/                  # FastAPI 后端
│   ├── main.py               # 入口，路由注册
│   ├── config.py             # 全局配置（端口、路径、日志）
│   ├── database.py           # SQLite 数据库连接
│   ├── models.py             # SQLAlchemy 模型定义
│   ├── schemas.py            # Pydantic 数据模型
│   ├── run_server.py         # 启动脚本
│   ├── routers/              # API 路由
│   │   ├── dataset.py        # 数据集管理
│   │   ├── finetune.py       # 微调任务
│   │   ├── evaluation.py     # 评测任务
│   │   ├── model.py          # 模型服务
│   │   └── ws.py             # WebSocket 实时进度
│   └── services/             # 业务逻辑
│       ├── dataset_service.py    # 数据集处理（上传/划分/转换）
│       ├── finetune_runner.py    # 微调执行器
│       ├── eval_runner.py        # 评测执行器
│       ├── model_runner.py       # 模型服务管理
│       ├── log_parser.py         # 训练日志解析
│       └── process_tracker.py    # 子进程管理
├── frontend/                 # Vue3 前端
│   └── src/
│       ├── views/            # 页面组件
│       ├── api/index.ts      # API 调用封装
│       └── router/index.ts   # 路由配置
├── data/                     # 数据存储
│   └── platform.db           # SQLite 数据库
├── saves/                    # 输出目录
│   ├── finetune_models/      # 微调权重
│   └── eval_results/         # 评测结果 CSV
├── yaml_templates/           # LLaMA-Factory YAML 模板
└── 示例代码/                  # 参考示例
```

## 快速启动

### 方式一：一键启动（推荐，仅 Linux）

```bash
# 首次运行需要添加执行权限
chmod +x start.sh stop.sh status.sh

# 后台启动（构建前端 + 启动后端，统一端口 18080）
./start.sh --bg

# 查看运行状态
./status.sh

# 查看日志
tail -f logs/backend.log

# 停止系统
./stop.sh
# 查看进程ID
pgrep -af "run_server.py"
```

打开浏览器访问 `http://服务器IP:18080`。

### 方式二：分别启动（开发调试）

#### 1. 后端

```bash
cd backend
conda activate Qwen311      # 激活 conda 环境
pip install -r requirements.txt
python run_server.py         # 默认端口 18080
```

#### 2. 前端

```bash
cd frontend
npm install
npm run dev                  # 默认端口 3003，监听 0.0.0.0
```

开发模式打开浏览器访问 `http://localhost:3003`。

---

## 功能说明

### 数据集管理
- 上传 CSV 数据集，支持设置图片路径前缀
- 在网页中直接制作数据集，自定义列名、字段类型、必填规则和默认值
- 明确映射 SFT 的 Prompt / Answer 或 DPO 的 Prompt / Chosen / Rejected 字段
- 支持逐条编辑、批量粘贴和上传图片，图片以数据集内相对路径保存，便于 Windows/Linux 迁移
- 支持选择整个图片文件夹，递归批量上传并为每张图片自动创建待标注数据行；上传前可给本批图片的指定列统一赋值
- 支持直接浏览管理员授权的 Linux 服务器目录并引用已有图片，无需经过浏览器重新上传；通过 `SERVER_BROWSE_ROOTS` 限制可见范围

`start.sh` 默认把 `/HTC/rws` 设置为服务器目录浏览白名单。如需改成多个目录，可在启动前覆盖，
例如 `SERVER_BROWSE_ROOTS=/HTC/rws,/mnt/datasets ./start.sh --bg`。
- 按比例随机划分训练集/测试集
- 自动转换为 LLaMA-Factory 可用的 JSON 格式
- 预览和编辑数据集（分页显示），点击行查看详情（图片渲染）

制作的数据集点击“保存、划分并用于训练”后，会生成 `train.csv`、`test.csv`、
`data.json` 和 `dataset_info.json`，随后可直接在“创建微调任务”中选择。每个数据集的
自定义列结构保存在其目录下的 `schema.json`；旧数据集没有该文件时仍使用列名自动识别。

DPO 数据集需要把字段分别映射为 `Prompt`、`Chosen` 和 `Rejected`。转换结果使用
`messages + chosen + rejected` 的偏好格式，并在 `dataset_info.json` 中自动写入
`ranking: true`。创建微调任务时选择 DPO，只能选择已转换的 DPO 数据集。

### 微调任务管理
- 选择数据集和基础模型，自动生成 YAML 训练配置
- 支持 SFT 监督微调和 DPO 偏好优化，任务与数据集类型自动校验
- DPO 支持配置 `pref_beta` 与 `pref_loss`
- 支持自定义 model_name_or_path、template、lora_target 等参数
- 调用 LLaMA-Factory 执行训练
- 实时显示训练进度（loss 曲线、step 数）
- 权重保存到 saves/finetune_models/

### 模型服务管理
- 使用 LLaMA-Factory API 模式启动推理服务
- 支持基础模型 + LoRA 权重加载
- 内置简单聊天界面，支持文本/图片输入测试
- 端口自动分配（18081-18100）

### 评测任务管理
- 选择已启动的模型服务 + 测试集
- 逐条调用模型 API 进行推理
- 自动提取预测结果（JSON 解析）
- 计算 Accuracy/Precision/Recall/F1/混淆矩阵
- 结果实时写入 CSV（saves/eval_results/）

## 环境要求

- Python 3.10+
- Node.js 18+
- LLaMA-Factory（需安装）
- sklearn（pip install scikit-learn）

## 端口说明

| 服务 | 端口 |
|------|------|
| 后端 API | 18080 |
| 前端页面 | 3003 |
| 模型服务 | 18081-18100（自动分配） |
