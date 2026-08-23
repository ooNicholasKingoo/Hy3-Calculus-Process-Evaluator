from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from hy3_eval.client import Hy3Client
from hy3_eval.dataset import load_dataset, write_dataset
from hy3_eval.evaluator import evaluate_process, reference_solution, run_benchmark

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "problems.jsonl"
if not DATA.exists(): write_dataset(DATA)
problems = load_dataset(DATA)
load_dotenv(ROOT / ".env")
has_hy3_key = bool(os.getenv("HY3_API_KEY"))

st.set_page_config(page_title="Hy3 微积分推理评估", page_icon="∫", layout="wide")
st.title("Hy3 微积分推理过程评估器")
st.caption("个人 / 犀牛鸟活动作品 · Hy3 生成可审查解答，确定性工具检查推导")
st.sidebar.subheader("Hy3 连接")
session_key = st.sidebar.text_input(
    "临时 API Key（不会保存）", type="password",
    help="如果没有配置项目根目录 .env，可在这里临时输入；只用于当前 Streamlit 会话。",
)
active_api_key = os.getenv("HY3_API_KEY") or session_key.strip()
active_model = os.getenv("HY3_MODEL", "hy3-295b")
if has_hy3_key:
    st.success(f"Hy3 在线模式 · {active_model} · {os.getenv('HY3_BASE_URL', 'https://tokenhub.tencentmaas.com/v1')}")
elif active_api_key:
    st.success(f"Hy3 在线模式（当前会话 Key） · {active_model}")
else:
    st.warning("当前未检测到 HY3_API_KEY：页面只能运行离线参考演示，不是 Hy3 生成结果。请在项目根目录 .env 中填写 Key 后重启服务。")
mode = st.sidebar.radio("工作台", ["单题评估", "批量评测", "结果分析"])

if mode == "单题评估":
    options = {f"{p.id} · {p.difficulty} · {p.prompt}": p for p in problems}
    selected = options[st.selectbox("选择题目", list(options))]
    st.info(f"题型：{selected.category}｜难度：{selected.difficulty}｜知识点：{', '.join(selected.tags)}")
    online_available = bool(active_api_key)
    offline = st.checkbox("使用离线参考答案演示（不调用 Hy3）", value=not online_available,
                          disabled=not online_available,
                          help="正式演示应关闭此选项并调用 Hy3。没有 API Key 时只能使用离线参考答案。")
    if st.button("开始评估", type="primary"):
        try:
            solution = reference_solution(selected) if offline else Hy3Client(api_key=active_api_key).solve(selected)
            result = evaluate_process(selected, solution)
            if offline:
                st.info("来源：离线参考答案。配置 HY3_API_KEY 后取消离线选项，才能展示 Hy3 的真实生成过程。")
            else:
                st.success("来源：Hy3 在线生成。以下步骤是模型返回的结构化可审查解答，不是隐藏思维链。")
            c1, c2, c3 = st.columns(3)
            c1.metric("最终答案", "正确" if result.final_answer.status == "valid" else "待检查")
            c2.metric("过程结论", "成立" if result.process_correct else "存在问题")
            c3.metric("首个错误步骤", result.first_error_step or "无")
            if result.answer_correct_but_process_invalid: st.warning("最终答案正确，但过程无法支撑该结论")
            if solution.method_summary:
                st.subheader("解题方法概述")
                st.write(solution.method_summary)
            if solution.assumptions:
                st.subheader("前提与条件")
                for assumption in solution.assumptions:
                    st.markdown(f"- {assumption}")
            st.subheader("完整解答过程")
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
    online_available = bool(active_api_key)
    offline = st.checkbox("离线参考答案（不调用 Hy3）", value=not online_available, disabled=not online_available)
    if st.button("运行批量评测", type="primary"):
        report = run_benchmark(problems, client=Hy3Client(api_key=active_api_key), offline=offline, limit=limit)
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
