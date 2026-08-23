from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from hy3_eval.client import Hy3Client
from hy3_eval.dataset import load_dataset, write_dataset
from hy3_eval.evaluator import evaluate_process, reference_solution, run_benchmark

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "problems.jsonl"
if not DATA.exists(): write_dataset(DATA)
problems = load_dataset(DATA)

st.set_page_config(page_title="Hy3 微积分推理评估", page_icon="∫", layout="wide")
st.title("Hy3 微积分推理过程评估器")
st.caption("个人 / 犀牛鸟活动作品 · 评估最终答案、推导链条与首个错误步骤")
mode = st.sidebar.radio("工作台", ["单题评估", "批量评测", "结果分析"])

if mode == "单题评估":
    options = {f"{p.id} · {p.difficulty} · {p.prompt}": p for p in problems}
    selected = options[st.selectbox("选择题目", list(options))]
    st.info(f"题型：{selected.category}｜知识点：{', '.join(selected.tags)}｜标准答案：{selected.standard_answer}")
    offline = st.checkbox("离线参考答案演示", value=True, help="关闭后使用 HY3_API_KEY 调用 Hy3")
    if st.button("开始评估", type="primary"):
        try:
            solution = reference_solution(selected) if offline else Hy3Client().solve(selected)
            result = evaluate_process(selected, solution)
            c1, c2, c3 = st.columns(3)
            c1.metric("最终答案", "正确" if result.final_answer.status == "valid" else "待检查")
            c2.metric("过程结论", "成立" if result.process_correct else "存在问题")
            c3.metric("首个错误步骤", result.first_error_step or "无")
            if result.answer_correct_but_process_invalid: st.warning("最终答案正确，但过程无法支撑该结论")
            for step, assessment in zip(solution.steps, result.steps):
                label = {"valid": "✅ 正确", "invalid": "❌ 错误", "uncertain": "⚠️ 待审查"}[assessment.status]
                with st.expander(f"步骤 {step.number} · {label}", expanded=True):
                    st.markdown(f"**前：** `{step.expression_before or ''}` → **后：** `{step.expression_after or ''}`")
                    st.write(step.explanation)
                    if step.theorem: st.caption(f"定理：{step.theorem}；条件：{step.condition or '未说明'}")
                    st.write(assessment.evidence)
        except Exception as exc:
            st.error(str(exc))

elif mode == "批量评测":
    limit = st.slider("题目数量", 1, len(problems), min(9, len(problems)))
    offline = st.checkbox("离线参考答案", value=True)
    if st.button("运行批量评测", type="primary"):
        report = run_benchmark(problems, offline=offline, limit=limit)
        st.session_state["report"] = report.model_dump()
        st.success(f"完成 {report.completed}/{report.total} 题，API 失败 {report.api_failures} 题")
        st.json({"最终答案准确率": report.final_answer_accuracy, "过程正确率": report.process_accuracy})

else:
    report_path = ROOT / "reports" / "latest_benchmark.json"
    if "report" in st.session_state: data = st.session_state["report"]
    elif report_path.exists(): data = json.loads(report_path.read_text(encoding="utf-8"))
    else: data = None
    if not data:
        st.info("请先在批量评测页运行一次实验。")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("最终答案准确率", f"{data['final_answer_accuracy']:.1%}")
        c2.metric("过程正确率", f"{data['process_accuracy']:.1%}")
        c3.metric("API 失败", data["api_failures"])
        rows = []
        for name, metrics in data.get("by_difficulty", {}).items(): rows.append({"难度": name, **metrics})
        if rows:
            st.subheader("按难度")
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
        st.subheader("错误类型分布")
        st.bar_chart(pd.Series(data.get("error_type_distribution", {}), name="数量"))
