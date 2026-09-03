from types import SimpleNamespace
from hy3_eval.client import parse_solution, Hy3Client, Hy3RequestError
from hy3_eval.client import Hy3Client
from hy3_eval.dataset import build_problems

def test_parse_json_solution():
    problem = build_problems()[0]
    result = parse_solution(problem, '{"final_answer":"1","method_summary":"用基本极限","assumptions":[],"steps":[{"number":1,"expression_before":"sin(x)/x","expression_after":"sin(x)/x","explanation":"保留原式"},{"number":2,"expression_before":"sin(x)/x","expression_after":"1","theorem":"基本极限","condition":"x趋近0","explanation":"使用基本极限"}]}')
    assert result.parse_error is None
    assert result.final_answer == "1"
    assert result.method_summary == "用基本极限"

def test_parse_markdown_wrapped_json():
    problem = build_problems()[0]
    result = parse_solution(problem, '```json\n{"final_answer":"1","steps":[{"number":1},{"number":2}]}\n```')
    assert result.parse_error is None

def test_reject_non_json():
    problem = build_problems()[0]
    result = parse_solution(problem, "not json")
    assert result.parse_error

def test_tokenhub_defaults(monkeypatch):
    monkeypatch.delenv("HY3_BASE_URL", raising=False)
    monkeypatch.delenv("HY3_MODEL", raising=False)
    client = Hy3Client(api_key="test-key")
    assert client.base_url == "https://tokenhub.tencentmaas.com/v1"
    assert client.model == "hy3"

def _response(content="OK"):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))], _request_id="req-test")

class FakeCompletions:
    def __init__(self, outcomes): self.outcomes, self.calls = list(outcomes), []
    def create(self, **kwargs):
        self.calls.append(kwargs); outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception): raise outcome
        return outcome

def _fake_client(outcomes):
    completions = FakeCompletions(outcomes)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions)), completions

class StatusError(Exception):
    def __init__(self, status_code, message="failure"):
        super().__init__(message); self.status_code = status_code; self.request_id = "req-status"

def test_session_key_is_used_by_client(monkeypatch):
    monkeypatch.setenv("HY3_API_KEY", "env-key")
    assert Hy3Client(api_key="session-key").api_key == "session-key"

def test_connection_success(monkeypatch):
    client = Hy3Client(api_key="test-key"); fake, _ = _fake_client([_response()])
    monkeypatch.setattr(client, "_client", lambda: fake)
    diagnostic = client.test_connection()
    assert diagnostic.status == "ok" and diagnostic.request_id == "req-test"

def test_connection_preflight_matches_tokenhub_curl(monkeypatch):
    client = Hy3Client(api_key="test-key")
    fake, completions = _fake_client([_response()])
    monkeypatch.setattr(client, "_client", lambda: fake)
    assert client.test_connection().status == "ok"
    request = completions.calls[0]
    assert request["model"] == "hy3"
    assert request["stream"] is False
    assert request["messages"][1]["content"] == "你好"
    assert "response_format" not in request
    assert "reasoning_effort" not in request

def test_authentication_error_does_not_retry(monkeypatch):
    client = Hy3Client(api_key="secret"); fake, completions = _fake_client([StatusError(401, "Bearer sk-secret is invalid")])
    monkeypatch.setattr(client, "_client", lambda: fake)
    diagnostic = client.test_connection()
    assert diagnostic.kind == "authentication" and diagnostic.retry_count == 0
    assert "sk-secret" not in diagnostic.message and len(completions.calls) == 1

def test_network_error_retries(monkeypatch):
    client = Hy3Client(api_key="test-key"); fake, completions = _fake_client([ConnectionError("connection refused"), ConnectionError("connection refused"), _response()])
    monkeypatch.setattr(client, "_client", lambda: fake)
    diagnostic = client.test_connection()
    assert diagnostic.status == "ok" and diagnostic.retry_count == 2 and len(completions.calls) == 3

def test_bad_request_falls_back_optional_parameters(monkeypatch):
    client = Hy3Client(api_key="test-key"); fake, completions = _fake_client([StatusError(400, "unsupported reasoning_effort"), StatusError(400, "unsupported response_format"), _response()])
    client.api_style = "chat"
    monkeypatch.setattr(client, "_client", lambda: fake)
    client._request(client._request_payload(build_problems()[0]))
    assert "reasoning_effort" in completions.calls[0]
    assert "reasoning_effort" not in completions.calls[1]
    assert "response_format" not in completions.calls[2]

def test_responses_api_shape_and_output_text(monkeypatch):
    class FakeResponses:
        def __init__(self): self.calls = []
        def create(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(output_text='{"final_answer":"1","steps":[{"number":1},{"number":2}]}', _request_id="req-responses")
    responses = FakeResponses()
    fake = SimpleNamespace(responses=responses, chat=SimpleNamespace(completions=FakeCompletions([])))
    client = Hy3Client(api_key="test-key", model="hy3")
    client.api_style = "responses"
    monkeypatch.setattr(client, "_client", lambda: fake)
    result = client.solve(build_problems()[0])
    assert result.parse_error is None
    assert responses.calls[0]["model"] == "hy3"
    assert responses.calls[0]["stream"] is False
    assert "instructions" in responses.calls[0] and "input" in responses.calls[0]

def test_non_json_model_response_is_response_parse(monkeypatch):
    problem = build_problems()[0]; client = Hy3Client(api_key="test-key"); fake, _ = _fake_client([_response("not JSON")])
    monkeypatch.setattr(client, "_client", lambda: fake)
    try: client.solve(problem)
    except Hy3RequestError as exc: assert exc.diagnostic.kind == "response_parse"
    else: raise AssertionError("expected Hy3RequestError")
