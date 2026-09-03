from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from dotenv import load_dotenv

from .models import CandidateSolution, CalculusProblem, ConnectionDiagnostic, SolutionStep, LLMJudgeResult

SYSTEM_PROMPT = """你是 Hy3 高等数学解题器，负责生成可审查的完整解答。
只输出一个 JSON 对象，不要 Markdown，不要输出隐藏思维链或无法验证的内部联想。
字段必须包含 final_answer、method_summary、assumptions、steps。
steps 按真实推导顺序排列为 4-12 步，每步必须包含 number、expression_before、expression_after、theorem、condition、explanation；可选返回 latex_before、latex_after、unicode_before、unicode_after 供页面排版。
每一步都要写出实际公式变换或定理应用，不能用“显然”“类似可得”替代关键推导。
如果使用洛必达、泰勒、换元、分部积分、隐函数求导或反常积分，必须明确写出适用条件。
答案面向大学高等数学学习者，解释详细但不泄露模型隐藏内部思维过程。"""

JUDGE_PROMPT = """你是高等数学解题过程评审专家。请审查另一段结构化解答，不要补写隐藏思维链，只根据题目、步骤和最终答案给出可复核结论。
请严格只输出 JSON：
{
  "is_correct": true 或 false,
  "error_step_index": 从0开始的首个错误步骤索引，没有确定错误则为 -1,
  "error_type": "question_misread|concept_error|calculation_error|condition_omission|jumped_derivation|logical_error|format_error|guessed_option|numerical_coincidence|theorem_misuse_correct_result|circular_reasoning|domain_convergence_omission|unsupported_claim|null",
  "is_lucky_guess": true 或 false,
  "explanation": "不超过120字的证据说明"
}
如果最终答案正确但步骤中误用定理、跳步、数值巧合或缺少必要条件，is_correct 必须为 false，is_lucky_guess 为 true。无法确定时 is_correct 为 null、error_step_index 为 -1。"""

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

def _safe_error_text(exc: Exception) -> str:
    text = re.sub(r"Bearer\s+\S+", "Bearer <redacted>", str(exc), flags=re.I)
    text = re.sub(r"sk-[A-Za-z0-9_-]+", "<redacted-key>", text)
    return text[:500] + ("..." if len(text) > 500 else "")

def _status_code(exc: Exception) -> int | None:
    value = getattr(exc, "status_code", None)
    if isinstance(value, int): return value
    response = getattr(exc, "response", None)
    value = getattr(response, "status_code", None)
    return value if isinstance(value, int) else None

def _request_id(exc: Exception) -> str | None:
    for attr in ("request_id", "x_request_id"):
        value = getattr(exc, attr, None)
        if value: return str(value)
    return None

def _classify_exception(exc: Exception) -> tuple[str, str, str]:
    status, text = _status_code(exc), _safe_error_text(exc).lower()
    if status == 401: return "authentication", "API Key 未通过认证。", "检查 TokenHub API Key 是否正确、有效且未过期。"
    if status == 403: return "permission", "API Key 没有调用该模型或接口的权限。", "检查 TokenHub 项目、模型权限和余额/配额。"
    if status == 404: return "model_not_found", "接口地址或模型不存在。", "检查 HY3_BASE_URL 和 HY3_MODEL 是否分别为 TokenHub v1 与 hy3。"
    if status == 429 or "rate limit" in text or "too many requests" in text: return "rate_limit", "请求触发限流。", "稍后重试，或降低批量请求速度。"
    if status == 400: return "bad_request", "请求参数不被接口接受。", "检查 response_format、reasoning_effort 和模型支持的请求格式。"
    if status is not None and status >= 500: return "server_error", f"TokenHub 服务端返回 HTTP {status}。", "稍后重试；若持续失败请检查 TokenHub 服务状态。"
    if isinstance(exc, (TimeoutError,)) or "timeout" in text or "timed out" in text: return "timeout", "连接或读取响应超时。", "检查网络、代理和防火墙；必要时增大 HY3_READ_TIMEOUT。"
    if "connection" in text or "connecterror" in text or "dns" in text or "name or service" in text: return "network", "无法连接 TokenHub。", "检查网络、代理、防火墙和 tokenhub.tencentmaas.com 的 443 端口可达性。"
    return "unknown", _safe_error_text(exc), "查看详细错误信息，并确认 Endpoint、模型和网络配置。"

class Hy3RequestError(RuntimeError):
    def __init__(self, diagnostic: ConnectionDiagnostic):
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic

class Hy3Client:
    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None):
        load_dotenv()
        self.api_key = (api_key or os.getenv("HY3_API_KEY", "")).strip()
        self.base_url = (base_url or os.getenv("HY3_BASE_URL", "https://tokenhub.tencentmaas.com/v1")).rstrip("/")
        self.model = (model or os.getenv("HY3_MODEL", "hy3")).strip()
        self.connect_timeout = float(os.getenv("HY3_CONNECT_TIMEOUT", "10"))
        self.timeout = float(os.getenv("HY3_READ_TIMEOUT", os.getenv("HY3_TIMEOUT", "90")))
        self.max_retries = max(0, int(os.getenv("HY3_MAX_RETRIES", "2")))
        self.reasoning_effort = os.getenv("HY3_REASONING_EFFORT", "high")
        # Keep the yesterday-verified TokenHub path as the default. Responses
        # API remains opt-in via HY3_API_STYLE=responses.
        self.api_style = os.getenv("HY3_API_STYLE", "chat").strip().lower()
        self.last_diagnostic: ConnectionDiagnostic | None = None

    def _client(self):
        if not self.api_key:
            raise RuntimeError("缺少 API Key。请在页面输入临时 Key，或在项目根目录 .env 配置 HY3_API_KEY。")
        from openai import OpenAI, Timeout
        timeout = Timeout(self.timeout, connect=self.connect_timeout)
        return OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=timeout)

    def _request(self, request: dict[str, Any], *, parse_json: bool = True) -> tuple[Any, ConnectionDiagnostic]:
        client, started, retries = self._client(), time.perf_counter(), 0
        variants = [request]
        if "response_format" in request or "reasoning_effort" in request:
            reduced = dict(request); reduced.pop("reasoning_effort", None); variants.append(reduced)
            plain = dict(reduced); plain.pop("response_format", None); variants.append(plain)
        last_exc: Exception | None = None
        for variant_index, variant in enumerate(variants):
            while True:
                try:
                    response = self._create_completion(client, variant)
                    # JSON is parsed by solve() after transport succeeds. Keeping
                    # transport and response-format failures separate makes the
                    # UI able to report malformed model output accurately.
                    diagnostic = ConnectionDiagnostic(status="ok", kind="unknown", message="Hy3 API 连接成功。", endpoint=self.base_url, model=self.model, elapsed_ms=int((time.perf_counter() - started) * 1000), retry_count=retries, request_id=getattr(response, "_request_id", None))
                    self.last_diagnostic = diagnostic
                    return response, diagnostic
                except Exception as exc:
                    last_exc = exc; kind, message, hint = _classify_exception(exc)
                    can_retry = kind in {"network", "timeout", "rate_limit", "server_error"} and retries < self.max_retries
                    if can_retry:
                        retries += 1; time.sleep(min(2.0, 0.4 * retries)); continue
                    if kind == "bad_request" and variant_index < len(variants) - 1: break
                    diagnostic = ConnectionDiagnostic(status="failed", kind=kind, message=message, endpoint=self.base_url, model=self.model, elapsed_ms=int((time.perf_counter() - started) * 1000), retry_count=retries, request_id=_request_id(exc), hint=hint)
                    self.last_diagnostic = diagnostic
                    raise Hy3RequestError(diagnostic) from exc
        raise Hy3RequestError(ConnectionDiagnostic(status="failed", kind="unknown", message=_safe_error_text(last_exc or RuntimeError("unknown error")), endpoint=self.base_url, model=self.model, retry_count=retries, hint="请检查 API 配置。"))

    def _create_completion(self, client, request: dict[str, Any]):
        payload = dict(request)
        style = payload.pop("_api_style", self.api_style)
        if style == "responses" and hasattr(client, "responses"):
            return client.responses.create(**payload)
        if style == "responses":
            instructions = payload.pop("instructions", None)
            user_input = payload.pop("input", "")
            payload["messages"] = ([{"role": "system", "content": instructions}] if instructions else []) + [{"role": "user", "content": user_input}]
        return client.chat.completions.create(**payload)

    @staticmethod
    def _response_text(response: Any) -> str:
        output_text = getattr(response, "output_text", None)
        if output_text is not None: return str(output_text)
        choices = getattr(response, "choices", None) or []
        return choices[0].message.content or "" if choices else ""

    def _request_payload(self, problem: CalculusProblem) -> dict[str, Any]:
        prompt = {"problem": problem.prompt, "category": problem.category, "expression": problem.expression, "point": problem.point, "lower": problem.lower, "upper": problem.upper}
        if self.api_style == "responses":
            return dict(_api_style="responses", model=self.model, instructions=SYSTEM_PROMPT,
                        input=json.dumps(prompt, ensure_ascii=False), stream=False)
        return dict(_api_style="chat", model=self.model, messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}], temperature=0.2, reasoning_effort=self.reasoning_effort, response_format={"type": "json_object"})

    def test_connection(self) -> ConnectionDiagnostic:
        # Keep the preflight request identical to the TokenHub curl example:
        # only model, messages, and stream are required.
        request = dict(_api_style="responses", model=self.model,
                       instructions="You are a helpful assistant.", input="你好", stream=False)
        try:
            _, diagnostic = self._request(request, parse_json=False); return diagnostic
        except Hy3RequestError as exc: return exc.diagnostic
        except Exception as exc:
            kind, message, hint = _classify_exception(exc)
            diagnostic = ConnectionDiagnostic(status="failed", kind=kind, message=message, endpoint=self.base_url, model=self.model, hint=hint)
            self.last_diagnostic = diagnostic; return diagnostic

    def solve(self, problem: CalculusProblem) -> CandidateSolution:
        response, _ = self._request(self._request_payload(problem), parse_json=True)
        text = self._response_text(response)
        result = parse_solution(problem, text)
        if result.parse_error:
            diagnostic = ConnectionDiagnostic(status="failed", kind="response_parse", message="API 已返回，但模型输出不符合要求的 JSON 解题格式。", endpoint=self.base_url, model=self.model, hint="检查模型输出内容，或稍后重试。")
            self.last_diagnostic = diagnostic; raise Hy3RequestError(diagnostic)
        return result

    def judge_process(self, problem: CalculusProblem, solution: CandidateSolution) -> LLMJudgeResult:
        """Ask Hy3 for a second-pass process review of a structured solution."""
        payload = {
            "problem": problem.prompt,
            "standard_answer": problem.standard_answer,
            "steps": [step.model_dump(exclude_none=True) for step in solution.steps],
            "final_answer": solution.final_answer,
        }
        request = {
            "_api_style": self.api_style,
            "model": self.model,
            "messages": [
                {"role": "system", "content": JUDGE_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "reasoning_effort": self.reasoning_effort,
        }
        if self.api_style == "responses":
            request = {"_api_style": "responses", "model": self.model,
                       "instructions": JUDGE_PROMPT,
                       "input": json.dumps(payload, ensure_ascii=False), "stream": False}
        response, _ = self._request(request, parse_json=True)
        text = self._response_text(response)
        try:
            data = _json_text(text)
            raw_type = data.get("error_type")
            return LLMJudgeResult(
                status="verified" if data.get("is_correct") is True else ("invalid" if data.get("is_correct") is False else "needs_review"),
                is_correct=data.get("is_correct"),
                error_step_index=int(data.get("error_step_index", -1)),
                error_type=None if raw_type in (None, "null", "") else str(raw_type),
                is_lucky_guess=bool(data.get("is_lucky_guess", False)),
                explanation=str(data.get("explanation", "")), raw_response=text,
            )
        except Exception as exc:
            raise Hy3RequestError(ConnectionDiagnostic(status="failed", kind="response_parse",
                message="Hy3 评审已返回，但评审 JSON 格式无法解析。", endpoint=self.base_url,
                model=self.model, hint="稍后重试评审，或仅依据规则校验结果。")) from exc
