# LLaMA-Factory 大模型微调说明文档  
**适用于 LLM / MLLM（如 Llama、Qwen、Qwen-VL、LLaVA 等）的高效微调**

---

## 一、简介

[LLaMA-Factory](https://github.com/hiyouga/LLaMA-Factory) 是一个开源、模块化、支持多后端的大语言模型微调框架，支持：
- **多种训练方法**：全参数微调（Full）、LoRA、QLoRA、AdaLoRA 等；
- **多种模型架构**：Llama、Mistral、Qwen、Baichuan、Phi、Gemma、**Qwen-VL、LLaVA** 等；
- **多模态支持**：图文理解（MLLM）微调；
- **高效训练**：集成 DeepSpeed、FSDP、vLLM 推理等；
- **简单易用**：YAML 配置 + 命令行启动。

> ✅ 本文档以 **Qwen2.5-VL-32B 多模态模型 LoRA 微调** 为例，涵盖数据准备、配置编写、训练与推理全流程。

---

## 二、环境准备

### 1. 安装依赖
```bash
git clone https://github.com/hiyouga/LLaMA-Factory.git
cd LLaMA-Factory
pip install -e ".[torch,metrics,vllm]"
# 或使用 pip install --upgrade llamafactory
```
## 模型与数据存放

- **模型路径**：`/HTC/rws/Qwen/Qwen2.5-VL-32B-Instruct`
- **数据目录**：`./data/`(其下有data.json和dataset_info.json)
- **输出目录**：`./saves/qwen2_5_vl_lora/`
- **配置文件**：`./Qwenvl2_5.yaml`

---

## 三、数据集制作

### 1. 构建data/data.json


```json
[
  {
    "messages": [
      {
        "role": "user",
        "content": "<image>Role: You are an intelligent assistant capable of accurately ......"
      },
      {
        "role": "assistant",
        "content": "### Analysis Process:\n\n1. **Identify Road Area**: The image shows a road inter......."
      }
    ],
    "images": [
            "/HTC/rws/model_tun/data/pic_pack/wupin/camera_11000000001317193402_20250629_230403.jpg"
        ]
  },
  {
    "messages": [
      {
        "role": "user",
        "content": "<image>Role: You are an intelligent assistant with the ability to recognize road......"
      },
      {
        "role": "assistant",
        "content": "### Analysis Process:\n\n1. **Identify Road Signs and Billboards:**\n   - The image co......."
      }
    ],
    "images": [
            "/HTC/rws/model_tun/data/pic_pack/gongbiao/S203顺密路K32+175建材市场西口 密云方向_20250522_082126.jpg"
        ]
  }
]
```
🔔 关键规则：
- 用户输入"role": "user","content"中必须包含占位符<image>；
- images 是图像文件的相对或绝对路径列表；
- 图像无需预处理，由 Qwen2VLProcessor 自动动态缩放。

### 2. 数据集注册（可选）

若使用自定义数据集名称，需在 data/dataset_info.json 中注册：

```json
 {
  "mllm_demo": {
    "file_name": "data.json",
    "formatting": "sharegpt",
    "columns": {
      "messages": "messages",
      "images": "images"
    },
    "tags": {
      "role_tag": "role",
      "content_tag": "content",
      "user_tag": "user",
      "assistant_tag": "assistant"
    }
  }
}
```


## 四、微调配置（YAML）

创建配置文件 Qwenvl2_5.yaml：
```
yaml
模型与模板
model_name_or_path: /path/to/Qwen2.5-VL-32B-Instruct
template: qwen2_vl                     # 模型问答时所使用的prompt模板，必须匹配模型类型
finetuning_type: lora                  # 使用 LoRA
lora_target: q_proj,v_proj             # 推荐仅微调注意力层

数据
dataset: mllm_demo             # 数据集在dataset_info.json对应的配置
dataset_info: ./data/dataset_info.json   #设置dataset_info（不写的话默认dataset_info.json）
overwrite_cache: true 
image_max_pixels: 1024                 # 关键：解决图片像素大小超过了配置文件中的预设，因此预设必须要高一些
val_size: 0.1                          # 验证集比例
overwrite_cache: true                  # 强制重新预处理
preprocessing_num_workers: 0           # 多模态必须设为 0！

训练
output_dir: ./saves/qwen2_5_vl_lora    # 输出的训练权重路径
per_device_train_batch_size: 1         # H800 可尝试 2
gradient_accumulation_steps: 8         # 等效 batch=8
learning_rate: 2e-5
num_train_epochs: 3
```
...(其余见Qwenvl2_5.yaml)

## 五、执行微调

启动训练
```bash
llamafactory-cli train Qwenvl2_5.yaml

#后台运行
nohup llamafactory-cli train Qwenvl2_5.yaml > train.log 2>&1 & 
tail -f train.log 
```


## 六、推理与部署

1. 命令行交互推理
```bash
llamafactory-cli chat \
    --model_name_or_path /HTC/rws/Qwen/Qwen3-VL-32B-Instruct \
    --adapter_name_or_path /HTC/rws/model_tun/output/qwen3_vl32B_finetuned \
    --template qwen2_vl \
    --infer_backend huggingface
```
输入时需包含 ：

User: 请描述这张图片。
(系统会提示上传图像)

2. 界面推理
```bash
llamafactory-cli webchat \
    --model_name_or_path /HTC/rws/Qwen/Qwen2.5-VL-32B-Instruct \
    --adapter_name_or_path /HTC/rws/model_tun/output/qwen2.5_vl32B_1.8data \
    --template qwen2_vl \
    --infer_backend huggingface


llamafactory-cli webchat \
    --model_name_or_path /HTC/rws/Qwen/Qwen3.5-VL-27B \
    --template qwen3_5 \
    --infer_backend huggingface

llamafactory-cli webchat \
    --model_name_or_path /HTC/rws/Qwen/tun/Qwen3.5-VL-27B-Baitan-Merged \
    --template qwen3_5 \
    --infer_backend huggingface

# 或者根据配置文件推理
llamafactory-cli webchat infer.yaml 
```

3. Python 脚本推理
启动推理服务
```bash
API_PORT=8000 llamafactory-cli api \
    --model_name_or_path /HTC/rws/Qwen/Qwen3.5-VL-27B \
    --adapter_name_or_path /HTC/rws/llama_factory/saves/Qwen/Qwen3.5-27B_DoRA_r16_attention_3.2data \
    --template qwen3_5 \
    --finetuning_type lora \
    --max_new_tokens 2048

API_PORT=8000 llamafactory-cli api \
    --model_name_or_path /HTC/rws/Qwen/Qwen3.6-27B \
    --template qwen3_5 \
    --max_new_tokens 2048

# 后台运行
API_PORT=8000 nohup llamafactory-cli api \
  --model_name_or_path /HTC/rws/Qwen/Qwen3.6-27B \
  --adapter_name_or_path /HTC/rws/llama_factory/saves/Qwen/Qwen3.6-27B_DoRA_r16_3.2data/checkpoint-500 \
  --template qwen3_6 \
  --max_new_tokens 3072 \
  > api.log 2>&1 &

# 查看日志  
tail -f api.log

# 杀死进程
ps aux | grep "llamafactory-cli" | grep -v grep # 先找到PID
kill -9 <PID> # 然后用输出的第二列数字执行

# 代码后台运行

nohup python qwen3.6_dora_r16_3.2data.py > qwen3.6_dora_r16_3.2data.log 2>&1 & echo $! > qwen3.6_dora_r16_3.2data.pid
tail -f qwen3.6_dora_r16_3.2data.log  #查看日志

# 调用接口脚本见/HTC/rws/llama_factory/llamafactory_inference/qwen3.5_dora_3.2data.py
```


4.模型合并

```bash
llamafactory-cli export \
    --model_name_or_path /HTC/rws/Qwen/Qwen3.5-VL-27B \
    --adapter_name_or_path /HTC/rws/llama_factory/saves/Qwen/Qwen3.5-27B_3_2data \
    --template qwen3_5 \
    --finetuning_type lora \
    --export_dir /HTC/rws/Qwen/tun/Qwen3.5-VL-27B-Baitan-Merged \
    --export_size 5 \
    --export_device auto
```

## 七、注意事项（多模态特别提醒）

1.  占位符不可省略  
   训练和推理时，prompt 中必须包含 <image> ，否则模型忽略图像。

2. 不要手动 resize 图像  
   让 Qwen2VLProcessor 自动处理分辨率，避免 token 数不匹配。

3. 禁用多进程预处理  
   preprocessing_num_workers 必须为 0，否则可能死锁或报错。

4. LoRA 不作用于视觉编码器  
   默认只微调语言模型部分，视觉 tower 保持冻结（符合最佳实践）。

## 八、参考资源

- GitHub: https://github.com/hiyouga/LlamaFactory/blob/main/data/mllm_demo.json
- 官方文档: https://llamafactory.readthedocs.io/zh-cn/latest/index.html 


