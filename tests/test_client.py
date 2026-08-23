from hy3_eval.client import parse_solution
from hy3_eval.dataset import build_problems

def test_parse_json_solution():
    problem = build_problems()[0]
    result = parse_solution(problem, '{"final_answer":"1","steps":[]}')
    assert result.parse_error is None
    assert result.final_answer == "1"

def test_parse_markdown_wrapped_json():
    problem = build_problems()[0]
    result = parse_solution(problem, '```json\n{"final_answer":"1","steps":[]}\n```')
    assert result.parse_error is None

def test_reject_non_json():
    problem = build_problems()[0]
    result = parse_solution(problem, "not json")
    assert result.parse_error
