# Hy3 Calculus Process Evaluator

Hy3 高等数学推理过程评估器是腾讯犀牛鸟开源实战活动的个人作品。它使用腾讯混元 Hy3 生成微积分解题过程，再用 SymPy 和数值方法检查答案、步骤关系与定理条件。

> 本项目为个人/活动作品，不代表腾讯官方产品。

## 范围

首版覆盖极限、导数/微分和积分，题目分为基础、中等、困难三层。评估结果区分最终答案正确、过程正确、首个错误步骤和“答案正确但过程不成立”。

## 题集说明

题集为 60 道微积分方向大学真题，覆盖大学真题中常见的极限、导数/微分和积分知识点，并按基础、中等、困难分层。每题保存题型、难度、知识点标签、标准答案、变量/积分区间、特殊校验元数据和构造说明。

- 基础层（20题）：基本极限、基本求导、基本不定积分与定积分，验证目标是建立符号校验基线。
- 中等层（20题）：等价无穷小、泰勒/洛必达、链式与隐函数求导、换元与分部积分，验证定理条件与中间变形。
- 困难层（20题）：高阶泰勒、复合极限、参数方程、二阶导数、反常积分与收敛条件，验证多知识点组合和定义域/收敛性。

分层依据是所需知识点数量、是否需要定理适用条件、是否包含参数/反常点以及标准答案校验的复杂度。最终答案由 SymPy 符号等价、导数回代、极限求值或定积分计算校验；文字性质题（如不可导性）使用文字标准答案与条件校验，不能强行套用表达式求导。

## 环境

- Python 3.12+
- `HY3_API_KEY`（运行真实 Hy3 请求时需要）
- TokenHub 默认接口：`https://tokenhub.tencentmaas.com/v1`
- TokenHub 默认模型：`hy3`（与 TokenHub curl 示例一致）
- TokenHub 默认调用方式：`chat`（昨天已验证的 `chat.completions` 路径）；如需测试 JavaScript 示例，可设置 `HY3_API_STYLE=responses`
- TokenHub Key 页面：[TokenHub 快速开始](https://console.cloud.tencent.com/tokenhub/quick-start?regionId=9)

## 安装与运行

### 下载后首次初始化（Windows PowerShell）

克隆仓库后，推荐先运行一次自动初始化脚本：

```powershell
git clone https://github.com/ooNicholasKingoo/hy3-math-evaluator.git
cd hy3-math-evaluator
powershell -ExecutionPolicy Bypass -File .\setup_app.ps1
```

脚本会检查 Python 3.12+、创建项目专用 `.venv`、安装依赖、检查模块并验证题集。项目不会上传或复用维护者的虚拟环境。

如果系统禁止执行 PowerShell 脚本，也可以只使用 Python 命令：

```powershell
cd D:\hy3-math-evaluator
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
# 在 .env 中填写 HY3_API_KEY
\.venv\Scripts\python.exe -m streamlit run app.py --server.port 8765
```

Windows 下也可以在项目目录执行 `powershell -ExecutionPolicy Bypass -File .\start_app.ps1`。脚本优先使用 `.venv`，并兼容当前旧目录 `venv`；它会检查 8765 端口、避免重复启动、启动后台 Streamlit 并打开浏览器。运行 `powershell -ExecutionPolicy Bypass -File .\check_app.ps1` 查看健康状态，运行 `powershell -ExecutionPolicy Bypass -File .\stop_app.ps1` 停止本项目占用的 Python 服务。若浏览器提示 localhost 拒绝连接，先运行启动脚本，不要只刷新旧页面。

最简单的启动方式是双击项目根目录中的 `run_app.cmd`。它会自动调用初始化脚本（首次运行时）、选择 `.venv` 或旧版 `venv`，检查端口并打开 `http://localhost:8765`。因此不需要激活虚拟环境，也不需要修改系统执行策略。`localhost` 是本机应用地址，不是部署在公网的固定网站；每次重启电脑后都要先运行 `run_app.cmd`，再打开浏览器地址。

项目环境目录说明：新下载项目使用 `.venv`；旧版本可能有 `venv`，启动脚本会临时兼容，但不应把任何虚拟环境提交到 Git。PowerShell 执行策略受限时，使用上面的 `powershell -ExecutionPolicy Bypass -File ...` 或直接使用 `.venv\Scripts\python.exe`。

也可以启动页面后，在左侧“Hy3 连接”中临时输入 TokenHub API Key。该输入只保存在当前会话内存中，不会写入文件；正式复现建议使用 `.env`。

页面显示“Hy3 已配置”只表示 Key 已输入，不代表网络连接已经成功。请先在侧边栏点击“测试 Hy3 连接”，确认连接通过后再开始评估。临时输入的 Key 优先于 `.env` 中的 Key。`regionId=1` 是腾讯云控制台区域参数，不应拼接到 API base_url；Endpoint 应填写 TokenHub 的 API 地址，默认是 `https://tokenhub.tencentmaas.com/v1`。默认连接预检和正式解题恢复为昨天已验证的 Chat Completions 路径；设置 `HY3_API_STYLE=responses` 才会使用 JavaScript 示例中的 Responses API。页面展示的是 Hy3 返回的结构化、可审查解答过程，包括方法概述、前提条件、每步公式变换、定理和解释；不会展示模型隐藏思维链。

## 公式显示

步骤中的数学表达式保留三种形式：`raw` 原始表达式用于 SymPy 校验，LaTeX 由页面主区域排版，Unicode 作为复制文本和无公式渲染环境的降级表示。页面使用 `st.latex` 展示分式、上下标、根式、积分、极限和导数；Hy3 也可以在步骤中返回可选的 `latex_before`、`latex_after`、`unicode_before`、`unicode_after` 字段。公式解析失败只显示原文并提示待复核，不会被当作数学错误，也不会改变确定性校验结果。当前版本不依赖 MathLive；如后续需要可编辑公式输入，再单独接入 MathLive 组件。

## 过程评估方式

过程评估采用两层机制。规则校验检查步骤数量（基础/中等题建议至少 3 步，困难题至少 5 步）、题目要求的方法关键词、相邻表达式关系和最终答案是否在步骤中自然导出；规则无法仅凭文本证明时标记为“需要复核”，不会直接判定数学错误。启用“Hy3 二次过程评审”后，Hy3 会以评审身份输出整体正确性、从 0 开始的首错步骤索引、错误类型、简短证据，以及是否属于“答案正确但过程不成立”。两层结果同时保留，便于比较确定性证据与模型审查意见。

错误分类只描述数学解题过程：题意误读、概念理解错误、计算错误、条件遗漏、跳步推导、逻辑推理错误和格式不符等。“格式不符”仅表示数学答题结构或书写规范不符合要求。Python/SymPy 的 `invalid syntax`、`TokenError` 等只作为底层校验证据，不会生成代码类错误类型，也不会进入数学错误分布；当自动校验无法比较相邻步骤时，页面只显示“需要人工复核”和简短技术证据。

连接失败排查：

- `authentication` / `permission`：检查 TokenHub Key、项目权限、余额和配额。
- `network` / `timeout`：检查网络、代理、防火墙以及 `tokenhub.tencentmaas.com:443` 是否可达。
- `model_not_found`：检查 `HY3_BASE_URL` 和 `HY3_MODEL`，默认分别为 TokenHub v1 和 `hy3`；控制台区域参数不属于 base_url。
- `rate_limit` / `server_error`：客户端会有限重试，仍失败时稍后再试。
- `bad_request`：客户端会依次去掉 `reasoning_effort` 和 `response_format` 兼容参数。
- `response_parse`：API 已返回，但模型输出不是要求的结构化 JSON，不属于网络错误。

## 过程评估器有效性验证

离线验证集包含 60 条可复现样本：20 条答案与过程均正确、20 条答案错误且首错步骤在第 2～4 步轮换、20 条最终答案正确但过程错误且首错步骤在第 2～5 步轮换。运行 `.\.venv\Scripts\python.exe -m hy3_eval.cli benchmark --offline --limit 60` 会生成 `reports/latest_benchmark.json` 和 `reports/validation_results.csv`，报告包括最终答案准确率、过程正确率、错误类型分布、错误样本检测率、首错定位准确率、正确样本误报率、答案正确但过程错误识别率，以及按题型和难度的分层结果。

验证集中的“人工审核”字段是当前 MVP 的明确标注基线，后续可以替换为真实人工抽检结果。离线参考答案用于验证评估器逻辑，不等同于 Hy3 在线模型能力测试。

离线运行题集校验和测试不需要 API Key：

```powershell
\.venv\Scripts\python.exe -m pytest -q
\.venv\Scripts\python.exe -m py_compile app.py hy3_eval\*.py
\.venv\Scripts\python.exe -m hy3_eval.cli validate-dataset
\.venv\Scripts\python.exe -m hy3_eval.cli benchmark --offline --limit 60
\.\check_app.ps1
```

真实模型评测：

```powershell
\.venv\Scripts\python.exe -m hy3_eval.cli benchmark --limit 3
```

批量评测的 `--limit` 只限制在线/离线题目基准结果；过程评估器的固定 60 条有效性验证样本仍会完整运行，避免小规模试跑扭曲检测率、定位率和误报率分母。

## 项目结构

- `hy3_eval/models.py`：题目、步骤和评估结果的数据模型
- `hy3_eval/validators.py`：极限、导数、积分的确定性校验器
- `hy3_eval/client.py`：Hy3 OpenAI 兼容 API 客户端
- `hy3_eval/evaluator.py`：解题、逐步评估和批量统计
- `data/problems.jsonl`：60 道微积分题
- `data/validation_cases.jsonl`：过程评估有效性验证样本
- `app.py`：Streamlit 应用
- `setup_app.ps1`：下载后的首次环境初始化
- `run_app.cmd`：Windows 用户双击启动入口

## 下载后验收

在全新目录中执行初始化后，可以不配置 API Key 直接验证离线功能：

```powershell
powershell -ExecutionPolicy Bypass -File .\setup_app.ps1
\.venv\Scripts\python.exe -m hy3_eval.cli benchmark --offline --limit 60
powershell -ExecutionPolicy Bypass -File .\start_app.ps1
Invoke-WebRequest http://localhost:8765
```

预期页面返回 HTTP 200，结果分析中能看到 60 条有效性验证明细、首错步骤和错误类型分布。在线模式是可选功能；只有在本地 `.env` 中填写 TokenHub Key 后，才会调用 Hy3。`.env`、`.venv`、`venv` 和任何真实 Key 均不应提交到 GitHub。

## 安全与限制

API Key 只能通过环境变量或本地 `.env` 传入，不能提交到 Git。无法由符号或数值方法可靠判断的步骤会标记为 `uncertain`，不会被自动当作正确。题集页面统一标注为“大学真题”，具体改编或参数化方式记录在 `construction` 字段中。
