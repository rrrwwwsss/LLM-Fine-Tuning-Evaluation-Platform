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

### 1. 后端

```bash
cd backend
conda activate Qwen        # 激活你的 Python 环境
pip install -r requirements.txt
python run_server.py        # 默认端口 18080
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev                 # 默认端口 3003
```

打开浏览器访问 `http://localhost:3003`。

---

## 功能说明

### 数据集管理
- 上传 CSV 数据集，支持设置图片路径前缀
- 按比例随机划分训练集/测试集
- 自动转换为 LLaMA-Factory 可用的 JSON 格式
- 预览数据集（分页显示），点击行查看详情（图片渲染）

### 微调任务管理
- 选择数据集和基础模型，自动生成 YAML 训练配置
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
