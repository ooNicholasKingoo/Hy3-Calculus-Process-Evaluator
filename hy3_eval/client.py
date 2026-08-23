from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv

from .models import CandidateSolution, CalculusProblem, SolutionStep

SYSTEM_PROMPT = """你是 Hy3 高等数学解题器，负责生成可审查的完整解答。
只输出一个 JSON 对象，不要 Markdown，不要输出隐藏思维链或无法验证的内部联想。
字段必须包含 final_answer、method_summary、assumptions、steps。
steps 按真实推导顺序排列为 4-12 步，每步必须包含 number、expression_before、expression_after、theorem、condition、explanation。
每一步都要写出实际公式变换或定理应用，不能用“显然”“类似可得”替代关键推导。
如果使用洛必达、泰勒、换元、分部积分、隐函数求导或反常积分，必须明确写出适用条件。
答案面向大学高等数学学习者，解释详细但不泄露模型隐藏内部思维过程。"""

def _json_text(text: str) -> dict[str, Any]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.I | re.M).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("model response is not JSON")
    return json.loads(text[start:end + 1])

def parse_solution(problem: CalculusProblem, text: str) -> CandidateSolution:
    try:
        payload = _json_text(text)
        steps = [SolutionStep.model_validate(s) for s in payload.get("steps", [])]
        if len(steps) < 2:
            raise ValueError("Hy3 返回的步骤少于 2 步，不符合完整解答要求")
        assumptions = payload.get("assumptions", [])
        if isinstance(assumptions, str): assumptions = [assumptions]
        return CandidateSolution(problem_id=problem.id, category=problem.category,
                                 final_answer=str(payload.get("final_answer", "")), steps=steps,
                                 method_summary=str(payload.get("method_summary", "")),
                                 assumptions=[str(x) for x in assumptions], raw_text=text)
    except Exception as exc:
        return CandidateSolution(problem_id=problem.id, category=problem.category, final_answer="",
                                 steps=[], raw_text=text, parse_error=str(exc))

class Hy3Client:
    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None):
        load_dotenv()
        self.api_key = api_key or os.getenv("HY3_API_KEY")
        # TokenHub is the Tencent Cloud gateway used by the activity API key.
        # Direct Hunyuan access remains configurable through HY3_BASE_URL.
        self.base_url = base_url or os.getenv("HY3_BASE_URL", "https://tokenhub.tencentmaas.com/v1")
        self.model = model or os.getenv("HY3_MODEL", "hy3")
        self.timeout = float(os.getenv("HY3_TIMEOUT", "90"))
        self.reasoning_effort = os.getenv("HY3_REASONING_EFFORT", "high")

    def solve(self, problem: CalculusProblem) -> CandidateSolution:
        if not self.api_key:
            raise RuntimeError("缺少 HY3_API_KEY；可使用 --offline 运行离线参考评测")
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=self.timeout)
        prompt = {"problem": problem.prompt, "category": problem.category, "expression": problem.expression,
                  "point": problem.point, "lower": problem.lower, "upper": problem.upper}
        request = dict(model=self.model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}],
            temperature=0.2,
            reasoning_effort=self.reasoning_effort)
        try:
            response = client.chat.completions.create(**request, response_format={"type": "json_object"})
        except Exception as exc:
            if "response_format" not in str(exc).lower() and "json" not in str(exc).lower():
                raise
            response = client.chat.completions.create(**request)
        text = response.choices[0].message.content or ""
        result = parse_solution(problem, text)
        if result.parse_error:
            raise ValueError(result.parse_error)
        return result
