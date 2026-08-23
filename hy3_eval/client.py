from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv

from .models import CandidateSolution, CalculusProblem, SolutionStep

SYSTEM_PROMPT = """你是严谨的高等数学解题器。只输出一个 JSON 对象，不要 Markdown。字段为 final_answer 字符串和 steps 数组。每个 step 包含 number、expression_before、expression_after、theorem、condition、explanation。必须写出完整可检查的推导，不得编造条件。"""

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
        return CandidateSolution(problem_id=problem.id, category=problem.category,
                                 final_answer=str(payload.get("final_answer", "")), steps=steps, raw_text=text)
    except Exception as exc:
        return CandidateSolution(problem_id=problem.id, category=problem.category, final_answer="",
                                 steps=[], raw_text=text, parse_error=str(exc))

class Hy3Client:
    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None):
        load_dotenv()
        self.api_key = api_key or os.getenv("HY3_API_KEY")
        self.base_url = base_url or os.getenv("HY3_BASE_URL", "https://api.hunyuan.cloud.tencent.com/v1")
        self.model = model or os.getenv("HY3_MODEL", "hy3-295b")
        self.timeout = float(os.getenv("HY3_TIMEOUT", "90"))

    def solve(self, problem: CalculusProblem) -> CandidateSolution:
        if not self.api_key:
            raise RuntimeError("缺少 HY3_API_KEY；可使用 --offline 运行离线参考评测")
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=self.timeout)
        prompt = {"problem": problem.prompt, "category": problem.category, "expression": problem.expression,
                  "point": problem.point, "lower": problem.lower, "upper": problem.upper}
        response = client.chat.completions.create(model=self.model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}],
            temperature=0.2, response_format={"type": "json_object"})
        text = response.choices[0].message.content or ""
        result = parse_solution(problem, text)
        if result.parse_error:
            raise ValueError(result.parse_error)
        return result
