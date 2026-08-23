# Hy3 Calculus Process Evaluator

Hy3 高等数学推理过程评估器是腾讯犀牛鸟开源实战活动的个人作品。它使用腾讯混元 Hy3 生成微积分解题过程，再用 SymPy 和数值方法检查答案、步骤关系与定理条件。

> 本项目为个人/活动作品，不代表腾讯官方产品。

## 范围

首版覆盖极限、导数/微分和积分，题目分为基础、中等、困难三层。评估结果区分最终答案正确、过程正确、首个错误步骤和“答案正确但过程不成立”。

## 环境

- Python 3.12+
- `HY3_API_KEY`（运行真实 Hy3 请求时需要）
- 默认接口：`https://api.hunyuan.cloud.tencent.com/v1`
- 默认模型：`hy3-295b`

## 安装与运行

```powershell
cd D:\hy3-math-evaluator
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# 在 .env 中填写 HY3_API_KEY
streamlit run app.py
```

离线运行题集校验和测试不需要 API Key：

```powershell
python -m pytest
python -m hy3_eval.cli validate-dataset
python -m hy3_eval.cli benchmark --offline
```

真实模型评测：

```powershell
python -m hy3_eval.cli benchmark --limit 3
```

## 项目结构

- `hy3_eval/models.py`：题目、步骤和评估结果的数据模型
- `hy3_eval/validators.py`：极限、导数、积分的确定性校验器
- `hy3_eval/client.py`：Hy3 OpenAI 兼容 API 客户端
- `hy3_eval/evaluator.py`：解题、逐步评估和批量统计
- `data/problems.jsonl`：60 道微积分题
- `data/validation_cases.jsonl`：过程评估有效性验证样本
- `app.py`：Streamlit 应用

## 安全与限制

API Key 只能通过环境变量或本地 `.env` 传入，不能提交到 Git。无法由符号或数值方法可靠判断的步骤会标记为 `uncertain`，不会被自动当作正确。题集为原创/程序化构造的活动评测材料，不构成教材或正式考试题库。
