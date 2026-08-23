from hy3_eval.client import parse_solution
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
