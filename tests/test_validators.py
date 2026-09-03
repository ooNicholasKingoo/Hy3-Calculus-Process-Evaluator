from hy3_eval.dataset import build_problems
from hy3_eval.evaluator import evaluate_process, reference_solution, rule_check_solution, merge_llm_judge
from hy3_eval.safe_math import equivalent, parse_expr
from hy3_eval.models import CandidateSolution, SolutionStep, LLMJudgeResult
from hy3_eval.evaluator import run_benchmark

def test_dataset_has_sixty_problems_and_three_levels():
    problems = build_problems()
    assert len(problems) == 60
    assert {p.difficulty for p in problems} == {"basic", "intermediate", "advanced"}
    assert {p.category for p in problems} == {"limit", "derivative", "integral"}
    assert {p.source for p in problems} == {"大学真题"}

def test_symbolic_parser_and_equivalence():
    assert equivalent(parse_expr("sin(x)**2 + cos(x)**2"), parse_expr("1"))

def test_reference_solution_is_process_valid_for_basic_samples():
    for problem in build_problems()[:10]:
        result = evaluate_process(problem, reference_solution(problem))
        assert result.final_answer.status == "valid"

def test_correct_answer_but_missing_step_is_not_process_valid():
    problem = build_problems()[7]
    solution = reference_solution(problem)
    solution.steps = []
    result = evaluate_process(problem, solution)
    assert result.final_answer.status == "valid"
    assert not result.process_correct

def test_wrong_intermediate_step_is_located_and_flagged():
    problem = build_problems()[7]
    solution = CandidateSolution(problem_id=problem.id, category=problem.category,
        final_answer=problem.standard_answer,
        steps=[SolutionStep(number=1, expression_before="x**3-2*x+1", expression_after="2"),
               SolutionStep(number=2, expression_before="2", expression_after="1")])
    result = evaluate_process(problem, solution)
    assert result.final_answer.status == "valid"
    assert result.first_error_step == 1
    assert result.process_summary is not None
    assert result.process_summary.primary_error_type == "计算错误"
    assert result.process_summary.explanation.startswith("错误开始于第 1 步")
    assert result.answer_correct_but_process_invalid
    assert any(issue.code == "calculation_error" for issue in result.steps[0].issues)

def test_step_continuity_and_order_are_reported():
    problem = build_problems()[0]
    solution = CandidateSolution(problem_id=problem.id, category=problem.category,
        final_answer=problem.standard_answer,
        steps=[SolutionStep(number=1, expression_before="sin(x)/x", expression_after="sin(x)/x"),
               SolutionStep(number=3, expression_before="x+1", expression_after="1")])
    result = evaluate_process(problem, solution)
    codes = {issue.code for step in result.steps for issue in step.issues}
    assert "step_order_error" in codes
    assert "continuity_error" in codes

def test_parse_failure_is_review_not_invalid_answer():
    problem = build_problems()[0]
    solution = CandidateSolution(problem_id=problem.id, category=problem.category,
        final_answer="", parse_error="model response is not JSON")
    result = evaluate_process(problem, solution)
    assert result.final_answer.status == "uncertain"
    assert result.review_status == "needs_review"
    assert result.first_error_step is None
    assert result.process_summary is not None
    assert result.process_summary.primary_error_type is None
    assert "API 返回的解答结构无法完成过程评估" in result.process_summary.explanation

def test_expression_parse_is_reported_as_math_review_not_code_error():
    problem = build_problems()[0]
    solution = CandidateSolution(
        problem_id=problem.id, category=problem.category,
        final_answer=problem.standard_answer,
        steps=[
            SolutionStep(number=1, expression_before="sin(x)/x", expression_after="x**"),
            SolutionStep(number=2, expression_before="x**", expression_after="1"),
        ],
    )
    result = evaluate_process(problem, solution)
    issues = [issue for step in result.steps for issue in step.issues]
    assert any(issue.code == "continuity_uncertain" for issue in issues)
    assert all(issue.error_type is None for issue in issues if issue.code == "continuity_uncertain")
    assert not any("表达式解析失败" in (issue.error_type or "") for issue in issues)
    assert not any(issue.error_type == "格式不符" and issue.code == "continuity_uncertain" for issue in issues)

def test_validation_metrics_are_computed_for_three_cohorts():
    report = run_benchmark(build_problems(), offline=True)
    assert report.validation_total == 60
    assert report.validation_first_error_detection_rate is not None
    assert report.validation_first_error_localization_accuracy is not None
    assert report.validation_false_positive_rate is not None
    assert report.validation_first_error_localization_accuracy == 1.0
    assert set(report.validation_by_kind) == {"correct", "wrong_answer", "correct_answer_wrong_process"}
    assert len(report.validation_results) == 60
    assert set(report.validation_by_difficulty) == {"basic", "intermediate", "advanced"}
    # The report exposes auditable denominators and actual/predicted steps.
    assert report.validation_wrong_answer_total == 20
    assert report.validation_wrong_answer_detected_count == 20
    assert report.validation_wrong_answer_localized_count == 20
    assert report.validation_answer_correct_total == 40
    assert report.validation_answer_correct_flagged_count == 20
    assert report.validation_answer_correct_true_problem_count == 20
    assert report.validation_answer_correct_false_positive_count == 0
    assert report.validation_false_positive_rate == 0.0
    assert report.validation_results[20]["actual_first_error_step"] == 2
    assert report.validation_results[20]["predicted_issue_step"] == 2
    assert len({row["actual_first_error_step"] for row in report.validation_results[20:40]}) > 1
    assert len({row["predicted_issue_step"] for row in report.validation_results[20:40]}) > 1


def test_validation_denominators_are_independent_of_benchmark_limit():
    report = run_benchmark(build_problems(), offline=True, limit=9)
    assert report.total == 9
    assert report.validation_total == 60
    assert report.validation_wrong_answer_total == 20
    assert report.validation_answer_correct_total == 40

def test_rule_checks_require_more_steps_for_advanced_problem():
    problem = next(p for p in build_problems() if p.difficulty == "advanced")
    solution = CandidateSolution(problem_id=problem.id, category=problem.category,
        final_answer=problem.standard_answer,
        steps=[SolutionStep(number=1, expression_before=problem.expression,
                            expression_after=problem.standard_answer)])
    checks = {item.code: item for item in rule_check_solution(problem, solution)}
    assert checks["step_count"].status == "uncertain"
    assert "5" in checks["step_count"].message

def test_llm_judge_can_supply_first_error_without_erasing_rule_evidence():
    problem = build_problems()[7]
    result = evaluate_process(problem, reference_solution(problem))
    judge = LLMJudgeResult(status="invalid", is_correct=False, error_step_index=0,
                           error_type="theorem_misuse_correct_result", is_lucky_guess=True,
                           explanation="首步定理条件未满足")
    merged = merge_llm_judge(result, judge)
    assert merged.first_error_step == 1
    assert merged.review_status == "invalid"
    assert merged.rule_checks
    assert "误用定理但得出正确结果" in merged.error_types
