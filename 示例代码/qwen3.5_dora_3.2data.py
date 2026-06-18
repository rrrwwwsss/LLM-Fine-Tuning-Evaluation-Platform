import pandas as pd
import json
import os
import csv
import re
import base64
import requests

# ======================
# 基础配置
# ======================
API_URL = "http://localhost:8000/v1/chat/completions"
# 随便填一个模型名，API服务通常不严格校验这个字段，但必须有
MODEL_NAME = "qwen-vl-finetuned" 

# 图片转 Base64 的辅助函数
def encode_image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# ======================
# API 调用函数
# ======================
def predict_via_api(image_path, prompt_text):
    print(f">>> 正在请求 API: {os.path.basename(image_path)}")
    
    base64_image = encode_image_to_base64(image_path)
    # 构造 OpenAI 格式的多模态请求
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt_text
                    }
                ]
            }
        ],
        "max_tokens": 2048,
        "temperature": 0.0  # 保证评测结果的确定性
    }

    try:
        response = requests.post(API_URL, json=payload, timeout=120)
        response.raise_for_status()
        result_json = response.json()
        generated_text = result_json['choices'][0]['message']['content']
        print("Generated Text:", generated_text)
        return extract_result(generated_text)
    except Exception as e:
        print(f"API 请求失败: {e}")
        return "错误"

# ======================
# 结果提取函数
# ======================
def extract_result(response):
    if isinstance(response, dict):
        return response.get("result", "错误")
    if isinstance(response, list) and response:
        response = response[-1]
        if isinstance(response, dict):
            return response.get("result", "错误")
    if isinstance(response, str):
        decoder = json.JSONDecoder()
        pos = 0
        all_results = []
        while True:
            match_index = response.find('{', pos)
            if match_index == -1:
                break
            try:
                result_data, end_index = decoder.raw_decode(response[match_index:])
                if isinstance(result_data, dict) and "result" in result_data:
                    all_results.append(result_data["result"])
                pos = match_index + 1
            except json.JSONDecodeError:
                pos = match_index + 1
        if all_results:
            return all_results[-1]
    return "错误"

if __name__ == "__main__":
    # ======================
    # 加载测试集
    # ======================
    test_csv = "/HTC/rws/model_tun/data/test_data.csv"
    df_test = pd.read_csv(test_csv)

    test_images = ["/HTC/rws/model_tun/data/pic_pack/" + p for p in df_test["image_path"].tolist()]
    test_images = [p.replace("\\", "/") for p in test_images]
    test_prompts = df_test["prompt_text"].tolist() 
    test_labels = [extract_result(x) for x in df_test["model_result"]]

    # ======================
    # 遍历测试集做对比
    # ======================
    csv_filename = "API_DoRA_Qwen_Finetuned_Only.csv"
    headers = ['true', 'ft', 'image_path']
    
    if not os.path.exists(csv_filename):
        with open(csv_filename, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()

    all_predictions = []
    index = 1
    
    for img, prompt, true_label in zip(test_images, test_prompts, test_labels):
        modified_text = re.sub(r"Output :.*?\.", "Output :", prompt)
        
        print(f"\n=== 处理第 {index} 条数据 ===")
        index += 1
        
        # 只请求微调后的模型接口
        result_ft = predict_via_api(img, modified_text)
        
        print('true:', true_label)
        print("ft:", result_ft)
        
        element = {
            'true': true_label,
            'ft': result_ft,
            'image_path': img
        }
        all_predictions.append(element)
        
        with open(csv_filename, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writerow(element)

    # ======================
    # 计算指标并保存
    # ======================
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
    def compute_metrics(y_true, y_pred):
        return {
            "accuracy": accuracy_score(y_true, y_pred),
            "precision": precision_score(y_true, y_pred, average='macro', zero_division=0),
            "recall": recall_score(y_true, y_pred, average='macro', zero_division=0),
            "f1": f1_score(y_true, y_pred, average='macro', zero_division=0)
        }

    preds_ft = [item['ft'] for item in all_predictions]
    metrics_ft = compute_metrics(test_labels, preds_ft)

    print("\n===== 微调后模型性能 =====")
    print(metrics_ft)

    with open("API_DoRA_Qwen_Metrics.txt", "w", encoding="utf-8") as f:
        f.write("===== 微调后模型性能 =====\n")
        f.write(str(metrics_ft) + "\n")