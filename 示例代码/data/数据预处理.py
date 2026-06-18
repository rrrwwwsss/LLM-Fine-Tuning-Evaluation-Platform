import pandas as pd
import json

# 读取 CSV 文件
df = pd.read_csv('/HTC/rws/model_tun/data/result_youxiao.csv')
test_images = ["/HTC/rws/model_tun/data/pic_pack/" + p for p in df["image_path"].tolist()]
test_images = [p.replace("\\", "/") for p in test_images]
# 创建目标格式的数据
data = []

# 遍历每一行并创建符合要求的字典
for idx, row in df.iterrows():
    path = "/HTC/rws/model_tun/data/pic_pack/" + row.get("image_path", "")
    path = path.replace("\\", "/")
    # entry = {
    #     "instruction": row.get("prompt_text", ""),  # 人类指令
    #     "input": "<image>",  # 输入字段空
    #     "output": row.get("model_result", ""),  # 模型回答
    #     "images": [path]  # 使用预处理后的路径
    # }
    entry = {
    "messages": [
      {
        "content": "<image>"+row.get("prompt_text", ""),
        "role": "user"
      },
      {
        "content": row.get("model_result", ""),
        "role": "assistant"
      },
    ],
    "images": [
      path,
    ]
  }
    data = [*data, entry]

# 将结果保存为 JSON 文件
with open('/HTC/rws/llama_factory/data/data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=4)

print("转换完成，结果保存在 data.json 文件中")