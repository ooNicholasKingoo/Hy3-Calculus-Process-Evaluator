from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from .client import Hy3Client
from .models import BenchmarkReport, CandidateSolution, CalculusProblem, EvaluationResult, SolutionStep
from .validators import assess_conditions, validate_final_answer, validate_step

def reference_solution(problem: CalculusProblem) -> CandidateSolution:
    steps = [SolutionStep(number=s.number, expression_before=s.expression_before,
                          expression_after=s.expression_after, theorem=s.theorem,
                          condition=s.condition, explanation=s.description)
             for s in problem.reference_steps]
    if not steps:
        # The final value is checked separately. For a definite integral, the
        # integrand and the scalar value are not a valid symbolic transition.
        after = problem.expression if problem.answer_type == "definite_integral" or problem.answer_mode == "text" else problem.standard_answer
        steps = [SolutionStep(number=1, expression_before=problem.expression,
                              expression_after=after, explanation="参考答案的可验证步骤")]
    return CandidateSolution(problem_id=problem.id, category=problem.category,
                             final_answer=problem.standard_answer, steps=steps,
                             method_summary="使用确定性参考解法生成离线演示步骤。",
                             assumptions=["参考答案仅用于离线演示，不代表 Hy3 输出"])

def evaluate_process(problem: CalculusProblem, solution: CandidateSolution, *, api_failed: bool = False) -> EvaluationResult:
    final = validate_final_answer(problem, solution)
    assessments = []
    first_error = None
    error_types: list[str] = []
    for step in solution.steps:
        assessment = validate_step(problem, step)
        condition = assess_conditions(problem, step)
        if assessment.status == "valid" and condition.status == "uncertain":
            assessment.status = "uncertain"
            assessment.error_type = condition.error_type
            assessment.evidence = condition.evidence
        if assessment.status == "invalid" and first_error is None:
            first_error = step.number
        if assessment.error_type and assessment.error_type not in error_types:
            error_types.append(assessment.error_type)
        assessments.append(assessment)
    for assessment in assessments:
        if first_error is not None and assessment.number > first_error and assessment.status == "invalid":
            assessment.affected = True
    process_correct = bool(assessments) and all(s.status == "valid" for s in assessments)
    return EvaluationResult(problem_id=problem.id, final_answer=final, steps=assessments,
                             process_correct=process_correct, first_error_step=first_error,
                             error_types=error_types,
                             answer_correct_but_process_invalid=final.status == "valid" and not process_correct,
                             api_failed=api_failed)

def _group_metrics(results: list[EvaluationResult], problems: dict[str, CalculusProblem], key: str) -> dict[str, dict[str, float]]:
    groups: dict[str, list[EvaluationResult]] = defaultdict(list)
    for result in results:
        groups[getattr(problems[result.problem_id], key)].append(result)
    return {name: {"count": float(len(items)),
                   "final_answer_accuracy": sum(x.final_answer.status == "valid" for x in items) / len(items),
                   "process_accuracy": sum(x.process_correct for x in items) / len(items)}
            for name, items in groups.items()}

def run_benchmark(problems: Iterable[CalculusProblem], client: Hy3Client | None = None,
                  *, offline: bool = False, limit: int | None = None) -> BenchmarkReport:
    selected = list(problems)[:limit] if limit else list(problems)
    client = client or Hy3Client()
    results: list[EvaluationResult] = []
    failures = 0
    for problem in selected:
        try:
            solution = reference_solution(problem) if offline else client.solve(problem)
            results.append(evaluate_process(problem, solution))
        except Exception as exc:
            failures += 1
            results.append(EvaluationResult(problem_id=problem.id,
                final_answer={"status": "uncertain", "expected": problem.standard_answer, "actual": "", "evidence": str(exc)},
                process_correct=False, api_failed=True, metadata={"error": str(exc)}))
    completed = [r for r in results if not r.api_failed]
    problem_map = {p.id: p for p in selected}
    errors = Counter(t for r in completed for t in r.error_types)
    invalid_steps = sum(any(step.status == "invalid" for step in r.steps) for r in completed)
    uncertain_steps = sum(any(step.status == "uncertain" for step in r.steps) for r in completed)
    return BenchmarkReport(total=len(selected), completed=len(completed), api_failures=failures,
        final_answer_accuracy=sum(r.final_answer.status == "valid" for r in completed) / len(completed) if completed else 0.0,
        process_accuracy=sum(r.process_correct for r in completed) / len(completed) if completed else 0.0,
        deterministic_error_rate=invalid_steps / len(completed) if completed else 0.0,
        uncertain_process_rate=uncertain_steps / len(completed) if completed else 0.0,
        by_difficulty=_group_metrics(completed, problem_map, "difficulty") if completed else {},
        by_category=_group_metrics(completed, problem_map, "category") if completed else {},
        error_type_distribution=dict(errors), results=results)
