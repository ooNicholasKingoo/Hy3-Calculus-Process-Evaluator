from hy3_eval.dataset import build_problems
from hy3_eval.evaluator import evaluate_process, reference_solution
from hy3_eval.safe_math import equivalent, parse_expr

def test_dataset_has_sixty_problems_and_three_levels():
    problems = build_problems()
    assert len(problems) == 60
    assert {p.difficulty for p in problems} == {"basic", "intermediate", "advanced"}
    assert {p.category for p in problems} == {"limit", "derivative", "integral"}

def test_symbolic_parser_and_equivalence():
    assert equivalent(parse_expr("sin(x)**2 + cos(x)**2"), parse_expr("1"))

def test_reference_solution_is_process_valid_for_basic_samples():
    for problem in build_problems()[:10]:
        result = evaluate_process(problem, reference_solution(problem))
        assert result.final_answer.status == "valid"

def test_correct_answer_but_missing_step_is_not_process_valid():
    problem = build_problems()[0]
    solution = reference_solution(problem)
    solution.steps = []
    result = evaluate_process(problem, solution)
    assert result.final_answer.status == "valid"
    assert not result.process_correct
