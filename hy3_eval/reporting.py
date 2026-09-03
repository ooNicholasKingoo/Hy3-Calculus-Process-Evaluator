"""Generate the reproducible offline analysis report from benchmark artifacts."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


DIFFICULTY_LABELS = {"basic": "基础", "intermediate": "中等", "advanced": "困难"}
CATEGORY_LABELS = {"limit": "极限", "derivative": "导数/微分", "integral": "积分"}
KIND_LABELS = {
    "correct": "答案与过程均正确",
    "wrong_answer": "答案错误",
    "correct_answer_wrong_process": "答案正确但过程错误",
}


def _pct(value: Any) -> str:
    return "—" if value is None else f"{float(value) * 100:.1f}%"


def _count(value: Any) -> int:
    return int(value or 0)


def generate_report(root: str | Path) -> Path:
    root = Path(root)
    report_path = root / "report.md"
    benchmark_path = root / "reports" / "latest_benchmark.json"
    csv_path = root / "reports" / "validation_results.csv"
    cases_path = root / "data" / "validation_cases.jsonl"
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    csv_rows = list(csv.DictReader(csv_path.open(encoding="utf-8-sig", newline=""))) if csv_path.exists() else []
    case_rows = [json.loads(line) for line in cases_path.read_text(encoding="utf-8").splitlines() if line.strip()] if cases_path.exists() else []

    by_kind = benchmark.get("validation_by_kind", {})
    by_diff = benchmark.get("by_difficulty", {})
    validation_by_diff = benchmark.get("validation_by_difficulty", {})
    distribution = benchmark.get("validation_error_type_distribution", {}) or benchmark.get("error_type_distribution", {})
    decline = benchmark.get("performance_decline_layer")
    lines: list[str] = [
        "# Hy3 微积分过程评估器离线分析报告",
        "",
        "> 本报告由 `hy3_eval.reporting` 根据项目内最新 JSON、CSV 和验证样本自动生成。它验证过程评估器在离线标准样本上的检测与定位能力，不等同于 Hy3 在线模型准确率。",
        "",
        "## 1. 数据范围与可复现性",
        "",
        f"- 题集基准：{_count(benchmark.get('total'))} 道，完成 {_count(benchmark.get('completed'))} 道，API 失败 {_count(benchmark.get('api_failures'))} 道。",
        f"- 有效性验证样本：JSON {len(case_rows)} 条，CSV {len(csv_rows)} 条；预期为 60 条。",
        "- 数据文件：`data/problems.jsonl`、`data/validation_cases.jsonl`、`reports/latest_benchmark.json`、`reports/validation_results.csv`。",
        "- 在线 Hy3 结果不会写入本报告；离线结果只说明确定性评估器和标注样本闭环可复现。",
        "",
        "验证集分为三组：",
        "",
        "| 样本组 | 数量 | 用途 |",
        "|---|---:|---|",
    ]
    for kind in ("correct", "wrong_answer", "correct_answer_wrong_process"):
        lines.append(f"| {KIND_LABELS[kind]} | {_count(by_kind.get(kind, {}).get('count'))} | " + {
            "correct": "检查正确过程误报",
            "wrong_answer": "检查问题检测和首错定位",
            "correct_answer_wrong_process": "检查答案正确但过程不成立识别",
        }[kind] + " |")

    lines += [
        "",
        "## 2. 过程评估方法设计依据",
        "",
        "1. 使用 SymPy 符号等价、导数回代、积分求导回代、定积分/极限计算验证最终答案。",
        "2. 对相邻步骤检查输入与上一步输出是否等价，并保留定理、条件和解释作为审查证据。",
        "3. 对洛必达、泰勒、换元、分部积分、反常积分等方法检查适用条件；无法确定时标记为待复核。",
        "4. 第一个确定为 `invalid` 的步骤是错误开始步骤，后续步骤标记为受前序错误影响。",
        "5. Python/SymPy 的解析异常只作为技术证据，不作为数学错误类型。",
        "",
        "## 3. 错误分类体系",
        "",
        "页面和报告使用中文名称，内部保留稳定代码：题意误读、概念理解错误、计算错误、条件遗漏/误用、跳步推导、逻辑推理错误、格式不符、猜中选项、数值巧合、误用定理但得出正确结果、循环论证、定义域或收敛条件遗漏、无依据结论。",
        "",
        "“格式不符”只描述数学书写或答题结构不规范；`invalid syntax`、`continuity_uncertain` 等底层信息不会进入数学错误分布。",
        "",
        "## 4. 有效性验证指标",
        "",
        "以下分母均由离线验证样本的标注组确定：",
        "",
        "| 指标 | 结果 | 分子/分母 |",
        "|---|---:|---|",
        f"| 答案错误样本过程问题检测率 | {_pct(benchmark.get('validation_first_error_detection_rate'))} | {_count(benchmark.get('validation_wrong_answer_detected_count'))}/{_count(benchmark.get('validation_wrong_answer_total'))} |",
        f"| 答案错误样本首错定位准确率 | {_pct(benchmark.get('validation_first_error_localization_accuracy'))} | {_count(benchmark.get('validation_wrong_answer_localized_count'))}/{_count(benchmark.get('validation_wrong_answer_total'))} |",
        f"| 最终答案正确样本误报率 | {_pct(benchmark.get('validation_answer_correct_false_positive_rate'))} | {_count(benchmark.get('validation_answer_correct_false_positive_count'))}/{_count(benchmark.get('validation_answer_correct_total'))} |",
        f"| 答案正确但过程错误识别率 | {_pct(benchmark.get('validation_answer_correct_process_invalid_rate'))} | {_count(benchmark.get('validation_answer_correct_true_problem_count'))}/{_count(benchmark.get('validation_answer_correct_total'))}（其中包含 20 条真实过程问题样本） |",
        f"| 所有验证样本人工标注真实问题比例 | {_pct(benchmark.get('validation_true_problem_rate'))} | 以 `human_review=真实问题` 计数 |",
        "",
        "### 分组明细",
        "",
        "| 样本组 | 数量 | 检测率 | 首错定位准确率 | 误报率 |",
        "|---|---:|---:|---:|---:|",
    ]
    for kind in ("correct", "correct_answer_wrong_process", "wrong_answer"):
        item = by_kind.get(kind, {})
        lines.append(f"| {KIND_LABELS[kind]} | {_count(item.get('count'))} | {_pct(item.get('process_issue_detection_rate'))} | {_pct(item.get('first_error_localization_accuracy')) if kind == 'wrong_answer' else '不适用'} | {_pct(item.get('false_positive_rate'))} |")

    lines += ["", "## 5. 题集基准与难度分层", "", "题集参考答案基准（不是在线 Hy3 能力）：", "", "| 难度 | 题数 | 最终答案准确率 | 过程正确率 |", "|---|---:|---:|---:|"]
    for difficulty in ("basic", "intermediate", "advanced"):
        item = by_diff.get(difficulty, {})
        lines.append(f"| {DIFFICULTY_LABELS[difficulty]} | {_count(item.get('count'))} | {_pct(item.get('final_answer_accuracy'))} | {_pct(item.get('process_accuracy'))} |")
    lines += ["", "能力临界点只在真实在线模型或人工标注输出上解释。当前报告的基准临界点字段为：" + (DIFFICULTY_LABELS.get(decline, decline) if decline else "未发现（没有低于 70% 或较上一层下降至少 15 个百分点）") + "。", ""]
    lines += ["有效性验证样本按题目难度的统计（用于检查样本覆盖，不用于推断模型能力）：", "", "| 难度 | 样本数 | 过程正确率 | 最终答案准确率 |", "|---|---:|---:|---:|"]
    for difficulty in ("basic", "intermediate", "advanced"):
        item = validation_by_diff.get(difficulty, {})
        lines.append(f"| {DIFFICULTY_LABELS[difficulty]} | {_count(item.get('count'))} | {_pct(item.get('process_accuracy'))} | {_pct(item.get('final_answer_accuracy'))} |")

    lines += ["", "## 6. 错误类型分布", "", "统计对象为验证样本中评估器预测的数学错误类型；API/解析失败不计入。", "", "| 错误类型 | 次数 |", "|---|---:|"]
    for label, count in sorted(distribution.items(), key=lambda item: (-int(item[1]), item[0])):
        lines.append(f"| {label} | {int(count)} |")

    lines += [
        "",
        "## 7. 典型案例与能力边界",
        "",
        "- 答案错误样本的人工首错步骤在第 2～4 步轮换；答案正确但过程错误样本在第 2～5 步轮换，避免把错误人为固定在第一步。",
        "- 对最终答案正确但过程无效的样本，评估器单独保留 `answer_correct_but_process_invalid` 标识。",
        "- 复杂参数、隐函数、反常积分、收敛条件和长链式推导仍可能需要人工复核；渲染或解析失败不等于数学错误。",
        "- 本次 60 条样本是可复现的离线标准夹具，不能替代真实 Hy3 输出的在线错误分布、能力下降区间或 API 稳定性结论。",
        "",
        "## 8. 复现实验",
        "",
        "```powershell",
        ".\\.venv\\Scripts\\python.exe -m hy3_eval.cli validate-dataset",
        ".\\.venv\\Scripts\\python.exe -m hy3_eval.cli benchmark --offline --limit 60",
        ".\\.venv\\Scripts\\python.exe -m pytest -q",
        "```",
        "",
        "运行 benchmark 会重新写入 JSON、CSV 和本报告；无需 API Key。",
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path

