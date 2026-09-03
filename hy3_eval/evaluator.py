from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from .client import Hy3Client
from .models import (BenchmarkReport, CandidateSolution, CalculusProblem, EvaluationResult,
                     SolutionStep, ProcessIssue, StepAssessment, ProcessSummary,
                     ERROR_TYPE_LABELS, error_type_label, RuleCheck, LLMJudgeResult)
from .validators import assess_conditions, validate_final_answer, validate_step
from .safe_math import equivalent, parse_expr
from .formula_renderer import render_formula, render_step_formulas
from .dataset import _build_validation_steps

def reference_solution(problem: CalculusProblem) -> CandidateSolution:
    steps = [SolutionStep(number=s.number, expression_before=s.expression_before,
                          expression_after=s.expression_after, theorem=s.theorem,
                          condition=s.condition, explanation=s.description,
                          latex_before=getattr(s, "latex_before", None),
                          latex_after=getattr(s, "latex_after", None),
                          unicode_before=getattr(s, "unicode_before", None),
                          unicode_after=getattr(s, "unicode_after", None))
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
    expected_display = render_formula(problem.standard_answer, variable=problem.variable)
    actual_display = render_formula(solution.final_answer, variable=problem.variable)
    final.expected_latex = expected_display.latex
    final.actual_latex = actual_display.latex
    final.expected_unicode = expected_display.unicode
    final.actual_unicode = actual_display.unicode
    final.formula_parse_status = "parsed" if expected_display.parse_status == "parsed" and actual_display.parse_status == "parsed" else "fallback"
    assessments = []
    first_error = None
    first_review = None
    error_types: list[str] = []
    parse_review = bool(solution.parse_error)

    # Legacy validator labels are normalized here so reports stay stable even
    # when a validator still emits its older, more technical wording.
    legacy_labels = {
        "代数/微积分计算错误": "计算错误",
        "无依据跳步": "跳步推导",
        "输出格式错误": "格式不符",
        "定理使用条件遗漏": "条件遗漏",
        "定义域或收敛条件遗漏": "定义域或收敛条件遗漏",
    }
    def normalize(label: str | None) -> str | None:
        if not label:
            return None
        return legacy_labels.get(label, error_type_label(label) or label)
    # Parse/API failures are review states, not proof that the mathematics is wrong.
    if solution.parse_error:
        issue = ProcessIssue(step_number=0, status="uncertain", error_type=None,
                             code="api_or_parse_error", evidence=f"Hy3 JSON 无法解析：{solution.parse_error}")
        assessments.append(StepAssessment(
            number=0, status="uncertain", error_type=issue.error_type, evidence=issue.evidence, issues=[issue]))
    if not solution.steps and not solution.parse_error:
        issue = ProcessIssue(step_number=0, status="uncertain", error_type="跳步推导",
                             code="missing_steps", evidence="没有返回任何可审查步骤，无法判断过程正确性")
        assessments.append(StepAssessment(number=0, status="uncertain", error_type=issue.error_type,
                                          evidence=issue.evidence, issues=[issue]))
        error_types.append(issue.error_type)
    numbers = [step.number for step in solution.steps]
    expected_numbers = list(range(1, len(numbers) + 1))
    structural_issue: dict[int, ProcessIssue] = {}
    if numbers != expected_numbers:
        for index, step in enumerate(solution.steps):
            if index >= len(expected_numbers) or step.number != expected_numbers[index]:
                structural_issue[step.number] = ProcessIssue(
                    step_number=step.number, status="invalid", error_type="格式不符",
                    code="step_order_error", evidence=f"步骤编号应连续为 {expected_numbers}，实际为 {numbers}")
                break
    previous = None
    seen_after: list[str] = []
    for step in solution.steps:
        assessment = validate_step(problem, step)
        issues: list[ProcessIssue] = []
        if assessment.error_type:
            # Existing validator finding is retained as an explicit issue code.
            code_map = {"代数/微积分计算错误": "calculation_error", "输出格式错误": "format_error",
                        "无依据跳步": "jumped_derivation", "定理使用条件遗漏": "condition_omission",
                        "定义域或收敛条件遗漏": "domain_convergence_omission"}
            code = code_map.get(assessment.error_type, "validation_uncertain" if assessment.status == "uncertain" else "validation_error")
            issues.append(ProcessIssue(step_number=step.number, status=assessment.status,
                                       error_type=normalize(assessment.error_type), code=code, evidence=assessment.evidence))
            assessment.error_type = normalize(assessment.error_type)
        condition = assess_conditions(problem, step)
        if condition.status == "uncertain":
            issues.append(ProcessIssue(step_number=step.number, status="uncertain",
                                       error_type=normalize(condition.error_type), code=condition.code,
                                       evidence=condition.evidence))
        if assessment.status == "valid" and condition.status == "uncertain":
            assessment.status = "uncertain"
            assessment.error_type = normalize(condition.error_type)
            assessment.evidence = condition.evidence
        if step.number in structural_issue:
            issues.append(structural_issue[step.number])
            assessment.status, assessment.error_type, assessment.evidence = "invalid", "格式不符", structural_issue[step.number].evidence
        # Adjacent steps must connect. An unparseable connection is reviewable;
        # a proven mismatch is an invalid chain.
        if previous and previous.expression_after and step.expression_before:
            try:
                if not equivalent(parse_expr(previous.expression_after, problem.variable),
                                  parse_expr(step.expression_before, problem.variable)):
                    issues.append(ProcessIssue(step_number=step.number, status="invalid", error_type="跳步推导",
                                               code="continuity_error", evidence="本步输入与上一步输出不等价，推理链在此处断开"))
                    assessment.status, assessment.error_type, assessment.evidence = "invalid", "跳步推导", "本步输入与上一步输出不等价，推理链在此处断开"
            except Exception as exc:
                evidence = f"相邻步骤的数学关系暂无法自动验证（底层解析信息：{type(exc).__name__}: {exc}）。请结合题意和推导说明人工复核。"
                issues.append(ProcessIssue(step_number=step.number, status="uncertain", error_type=None,
                                           code="continuity_uncertain", evidence=evidence))
                if assessment.status == "valid":
                    assessment.status, assessment.error_type, assessment.evidence = "uncertain", None, evidence
        if step.expression_after and step.expression_after in seen_after:
            issues.append(ProcessIssue(step_number=step.number, status="uncertain", error_type="循环论证",
                                       code="circular_reasoning", evidence="本步重复使用了此前已经得到的表达式，缺少新的可验证依据"))
            if assessment.status == "valid":
                assessment.status, assessment.error_type, assessment.evidence = "uncertain", "循环论证", "重复表达式需要人工确认是否构成循环论证"
        if not step.expression_before or not step.expression_after:
            issues.append(ProcessIssue(step_number=step.number, status="uncertain", error_type="跳步推导",
                                       code="jumped_derivation", evidence="缺少完整的前后表达式，无法审查关键变换"))
            if assessment.status == "valid":
                assessment.status, assessment.error_type, assessment.evidence = "uncertain", "跳步推导", "缺少完整的前后表达式，无法审查关键变换"
        assessment.issues = issues
        before_display, after_display = render_step_formulas(step, problem.variable)
        assessment.latex_before = before_display.latex
        assessment.latex_after = after_display.latex
        assessment.unicode_before = before_display.unicode
        assessment.unicode_after = after_display.unicode
        assessment.formula_parse_status = "parsed" if before_display.parse_status == "parsed" and after_display.parse_status == "parsed" else "fallback"
        if assessment.status == "invalid" and first_error is None:
            first_error = step.number
        if assessment.status == "uncertain" and first_review is None:
            first_review = step.number
        for found in [assessment.error_type, *(issue.error_type for issue in issues)]:
            found = normalize(found)
            if found and found not in error_types:
                error_types.append(found)
        assessments.append(assessment)
        previous = step
        if step.expression_after:
            seen_after.append(step.expression_after)
    for assessment in assessments:
        if first_error is not None and assessment.number > first_error and assessment.status == "invalid":
            assessment.affected = True
            for issue in assessment.issues:
                issue.affected = True
    process_correct = bool(solution.steps) and all(s.status == "valid" for s in assessments if s.number != 0)
    review_status = "invalid" if first_error is not None else ("verified" if process_correct else "needs_review")
    primary = None
    if first_error is not None:
        primary = next((normalize(a.error_type) for a in assessments if a.number == first_error and a.error_type), None)
    elif first_review is not None:
        primary = next((normalize(a.error_type) for a in assessments if a.number == first_review and a.error_type), None)
    if primary is None and error_types:
        primary = error_types[0]
    if first_error is not None:
        explanation = f"错误开始于第 {first_error} 步。" + (f"主要错误类型是“{primary}”。" if primary else "")
    elif parse_review:
        explanation = "API 返回的解答结构无法完成过程评估，请重新请求或人工检查原始回答；这不是数学错误类型。"
    elif first_review is not None:
        explanation = f"第 {first_review} 步存在待复核问题，当前不能直接判定为数学错误。"
    elif process_correct:
        explanation = "未发现确定性错误，过程通过自动校验。"
    elif error_types:
        explanation = f"当前解答无法完成完整过程审查，主要问题类型是“{primary or error_types[0]}”。"
    else:
        explanation = "解答步骤不足，无法完成过程正确性判定。"
    summary = ProcessSummary(status=review_status, first_error_step=first_error,
                             first_review_step=first_review, primary_error_type=primary,
                             error_types=error_types, explanation=explanation)
    result = EvaluationResult(problem_id=problem.id, final_answer=final, steps=assessments,
                             process_correct=process_correct, first_error_step=first_error,
                             first_review_step=first_review, review_status=review_status,
                             error_types=error_types,
                             answer_correct_but_process_invalid=final.status == "valid" and not process_correct,
                             api_failed=api_failed, process_summary=summary)
    result.rule_checks = rule_check_solution(problem, solution)
    return result


_RULE_KEYWORDS = {
    "基本极限": ["极限"], "等价无穷小": ["等价", "无穷小"], "泰勒展开": ["泰勒"],
    "高阶泰勒": ["泰勒"], "洛必达": ["洛必达"], "链式法则": ["链式", "复合"],
    "乘积法则": ["乘积"], "商法则": ["商法"], "隐函数求导": ["隐函数", "求导"],
    "参数方程": ["参数", "dy/dx"], "换元": ["换元"], "分部积分": ["分部积分"],
    "反常积分": ["反常", "收敛"], "收敛条件": ["收敛"], "导数定义": ["导数", "定义"],
    "复合极限": ["极限"], "高阶导数": ["二阶", "高阶", "导数"],
    "复合函数": ["链式", "复合", "求导"], "不可导点": ["不可导", "左右导数"],
    "级数": ["级数", "收敛"], "参数技巧": ["参数", "对称"], "有理化": ["有理化"],
    "基本求导": ["求导"], "基本积分": ["积分"], "定积分": ["积分"],
    "对数求导": ["对数", "求导"], "对数函数": ["对数", "导数"],
}


def rule_check_solution(problem: CalculusProblem, solution: CandidateSolution) -> list[RuleCheck]:
    """Advisory, deterministic checks that complement symbolic validation.

    These checks deliberately use ``uncertain`` for missing explanatory
    evidence. They never replace the raw SymPy verdict or claim a theorem is
    false merely because the model omitted a keyword.
    """
    checks: list[RuleCheck] = []
    target_steps = problem.minimum_steps
    count = len(solution.steps)
    checks.append(RuleCheck(code="step_count", status="valid" if count >= target_steps else "uncertain",
                            message=f"步骤数量 {count}/{target_steps}",
                            evidence="达到该难度层建议的最少步骤数。" if count >= target_steps else "步骤较少，可能存在跳步，建议结合 Hy3 评审复核。"))
    text = " ".join(filter(None, [solution.method_summary, *solution.assumptions,
                                  *(f"{s.theorem or ''} {s.condition or ''} {s.explanation or ''}" for s in solution.steps)]))
    required: list[str] = []
    for tag in problem.tags:
        required.extend(_RULE_KEYWORDS.get(tag, []))
    missing = sorted({keyword for keyword in required if keyword.lower() not in text.lower()})
    checks.append(RuleCheck(code="key_formula_keywords", status="valid" if not missing else "uncertain",
                            message="关键方法/公式关键词检查",
                            evidence="已出现：" + "、".join(required) if not missing else "缺少：" + "、".join(missing)))
    final_in_steps = False
    if solution.final_answer and problem.answer_mode == "expression":
        try:
            expected = parse_expr(solution.final_answer, problem.variable)
            final_in_steps = any(step.expression_after and equivalent(expected, parse_expr(step.expression_after, problem.variable)) for step in solution.steps)
        except Exception:
            final_in_steps = False
    elif solution.final_answer:
        final_in_steps = any(solution.final_answer.strip() in (step.expression_after or "") for step in solution.steps)
    checks.append(RuleCheck(code="final_answer_derivation", status="valid" if final_in_steps else "uncertain",
                            message="最终答案是否在步骤中自然出现",
                            evidence="最终答案可在步骤结果中找到。" if final_in_steps else "最终答案未在步骤结果中明确出现，建议复核是否存在跳步。"))
    return checks


def merge_llm_judge(result: EvaluationResult, judge: LLMJudgeResult) -> EvaluationResult:
    """Attach Hy3's second-pass review without erasing deterministic evidence."""
    result.llm_judge = judge
    result.metadata["llm_judge_status"] = judge.status
    if judge.error_type:
        label = error_type_label(judge.error_type) or judge.error_type
        if label not in result.error_types:
            result.error_types.append(label)
    if judge.is_lucky_guess:
        result.answer_correct_but_process_invalid = True
        if "答案正确但过程不成立" not in result.error_types:
            result.error_types.append("答案正确但过程不成立")
    if judge.status == "invalid" and result.first_error_step is None:
        step = judge.error_step_index + 1 if judge.error_step_index >= 0 else None
        if step is not None:
            result.first_error_step = step
            result.review_status = "invalid"
            result.process_correct = False
            result.answer_correct_but_process_invalid = result.final_answer.status == "valid"
            result.process_summary = ProcessSummary(
                status="invalid", first_error_step=step,
                primary_error_type=error_type_label(judge.error_type) or judge.error_type,
                error_types=result.error_types,
                explanation=f"Hy3 评审认为错误开始于第 {step} 步。{judge.explanation}".strip(),
            )
    elif judge.status == "needs_review" and result.review_status == "verified":
        result.review_status = "needs_review"
        result.process_correct = False
        result.process_summary = ProcessSummary(status="needs_review", first_review_step=judge.error_step_index + 1 if judge.error_step_index >= 0 else None,
                                                 primary_error_type=error_type_label(judge.error_type) or judge.error_type,
                                                 error_types=result.error_types,
                                                 explanation=judge.explanation or "Hy3 评审要求人工复核。")
    return result

def _group_metrics(results: list[EvaluationResult], problems: dict[str, CalculusProblem], key: str) -> dict[str, dict[str, float]]:
    groups: dict[str, list[EvaluationResult]] = defaultdict(list)
    for result in results:
        groups[getattr(problems[result.problem_id], key)].append(result)
    return {name: {"count": float(len(items)),
                   "final_answer_accuracy": sum(x.final_answer.status == "valid" for x in items) / len(items),
                   "process_accuracy": sum(x.process_correct for x in items) / len(items)}
            for name, items in groups.items()}

def _validation_rows(problems: list[CalculusProblem], results: list[EvaluationResult]) -> list[dict]:
    """Create deterministic validation rows from the three labelled cohorts.

    The cohorts intentionally exercise the evaluator: correct reference
    solutions, wrong intermediate calculations, and answers that are right but
    have an invalid/missing process. No API call is needed for this check.
    """
    rows: list[dict] = []
    for index, (problem, result) in enumerate(zip(problems, results), 1):
        cohort_index = ((index - 1) % 60) + 1
        if cohort_index <= 20:
            kind, expected_step, expected_types, human = "correct", None, [], "未发现问题"
        elif cohort_index <= 40:
            kind, expected_step, expected_types, human = (
                "wrong_answer", 2 + ((cohort_index - 21) % 3), ["计算错误"], "真实问题"
            )
        else:
            kind, expected_step, expected_types, human = (
                "correct_answer_wrong_process", 2 + ((cohort_index - 41) % 4), ["跳步推导"], "真实问题"
            )
        predicted_types = result.error_types
        predicted_issue_step = result.first_error_step or result.first_review_step
        detected = (predicted_issue_step is not None) if expected_step is not None else (not result.process_correct)
        localized = expected_step is not None and predicted_issue_step == expected_step
        rows.append({
            "problem_id": problem.id, "kind": kind, "difficulty": problem.difficulty,
            "category": problem.category, "standard_answer": problem.standard_answer,
            "expected_first_error_step": expected_step, "predicted_first_error_step": result.first_error_step,
            "actual_first_error_step": expected_step,
            "predicted_deterministic_error_step": result.first_error_step,
            "predicted_first_review_step": result.first_review_step,
            "predicted_issue_step": predicted_issue_step,
            "first_error_detected": detected, "first_error_localized": localized,
            "expected_error_types": expected_types, "predicted_error_types": predicted_types,
            "final_answer_status": result.final_answer.status,
            "process_correct_expected": kind == "correct", "process_correct_predicted": result.process_correct,
            "human_review": human, "false_positive": kind == "correct" and not result.process_correct,
            "answer_correct_but_process_invalid": result.answer_correct_but_process_invalid,
        })
    return rows

def _validation_solution(problem: CalculusProblem, index: int) -> CandidateSolution:
    """Build one deterministic labelled sample for evaluator validity checks."""
    if index <= 20:
        return reference_solution(problem)
    if index <= 40:
        error_step = 2 + ((index - 21) % 3)
        steps = _build_validation_steps(problem, error_step, keep_final=False)
        return CandidateSolution(
            problem_id=problem.id, category=problem.category,
            final_answer="0",
            steps=[SolutionStep.model_validate(step) for step in steps],
            method_summary=f"验证样本（答案错误过程，第 {error_step} 步注入错误）")
    error_step = 2 + ((index - 41) % 4)
    steps = _build_validation_steps(problem, error_step, keep_final=True)
    return CandidateSolution(
        problem_id=problem.id, category=problem.category,
        final_answer=problem.standard_answer,
        steps=[SolutionStep.model_validate(step) for step in steps],
        method_summary=f"验证样本（答案正确但过程错误，第 {error_step} 步省略关键推导）")

def _validation_summary(rows: list[dict]) -> tuple[dict[str, dict[str, float]], dict[str, int]]:
    by_kind: dict[str, dict[str, float]] = {}
    for kind in sorted({r["kind"] for r in rows}):
        items = [r for r in rows if r["kind"] == kind]
        by_kind[kind] = {
            "count": float(len(items)),
            "process_issue_detection_rate": sum(bool(r["first_error_detected"]) for r in items) / len(items),
            "first_error_localization_accuracy": sum(bool(r["first_error_localized"]) for r in items) / len(items) if kind == "wrong_answer" else 0.0,
            "false_positive_rate": sum(bool(r["false_positive"]) for r in items) / len(items),
        }
    error_distribution = Counter(t for r in rows for t in r["predicted_error_types"])
    return by_kind, dict(error_distribution)

def _validation_difficulty(rows: list[dict]) -> tuple[dict[str, dict[str, float]], str | None]:
    order = ["basic", "intermediate", "advanced"]
    result: dict[str, dict[str, float]] = {}
    decline: str | None = None
    previous: float | None = None
    for difficulty in order:
        items = [r for r in rows if r["difficulty"] == difficulty]
        if not items:
            continue
        process_accuracy = sum(bool(r["process_correct_predicted"]) for r in items) / len(items)
        final_accuracy = sum(r["final_answer_status"] == "valid" for r in items) / len(items)
        result[difficulty] = {"count": float(len(items)), "process_accuracy": process_accuracy,
                              "final_answer_accuracy": final_accuracy}
        if previous is not None and (process_accuracy < 0.7 or previous - process_accuracy >= 0.15) and decline is None:
            decline = difficulty
        previous = process_accuracy
    return result, decline

def _performance_decline_layer(metrics: dict[str, dict[str, float]]) -> str | None:
    """Find the first difficulty layer where real benchmark performance drops."""
    previous: float | None = None
    for difficulty in ("basic", "intermediate", "advanced"):
        if difficulty not in metrics:
            continue
        current = metrics[difficulty].get("process_accuracy", 0.0)
        if current < 0.7 or (previous is not None and previous - current >= 0.15):
            return difficulty
        previous = current
    return None

def run_benchmark(problems: Iterable[CalculusProblem], client: Hy3Client | None = None,
                  *, offline: bool = False, limit: int | None = None) -> BenchmarkReport:
    # Keep the model benchmark limit independent from evaluator validity
    # validation.  A quick 9-question run must not silently turn the fixed
    # 60-case validation set into a mostly-correct subset with no localization
    # denominator.
    all_problems = list(problems)
    selected = all_problems[:limit] if limit else all_problems
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
    validation_results = [evaluate_process(p, _validation_solution(p, index)) for index, p in enumerate(all_problems, 1)]
    validation_rows = _validation_rows(all_problems, validation_results)
    validation_by_kind, validation_error_distribution = _validation_summary(validation_rows)
    validation_by_difficulty, _ = _validation_difficulty(validation_rows)
    benchmark_by_difficulty = _group_metrics(completed, problem_map, "difficulty") if completed else {}
    # 首错检测/定位的分母严格限定为“最终答案错误”样本；“答案正确但
    # 过程错误”是另一类能力，单独通过 answer_correct_* 指标统计。
    wrong_rows = [r for r in validation_rows if r["kind"] == "wrong_answer"]
    correct_rows = [r for r in validation_rows if r["kind"] == "correct"]
    invalid_answer_process_rows = [r for r in validation_rows if r["kind"] == "correct_answer_wrong_process"]
    wrong_answer_detected = sum(bool(r["first_error_detected"]) for r in wrong_rows)
    wrong_answer_localized = sum(bool(r["first_error_localized"]) for r in wrong_rows)
    correct_flagged = sum(not r["process_correct_predicted"] for r in correct_rows)
    correct_true_problem = sum(r["human_review"] == "真实问题" for r in correct_rows)
    false_positive = sum(bool(r["false_positive"]) for r in correct_rows)
    # The requested false-positive analysis is based on all samples with a
    # correct final answer.  This includes both clean correct samples and the
    # deliberately invalid-process cohort, so a detector can be measured on
    # both true positives and false positives.
    answer_correct_rows = [r for r in validation_rows if r["final_answer_status"] == "valid"]
    answer_correct_flagged = sum(not r["process_correct_predicted"] for r in answer_correct_rows)
    answer_correct_true_problem = sum(r["human_review"] == "真实问题" for r in answer_correct_rows)
    answer_correct_false_positive = sum(
        (r["human_review"] != "真实问题") and (not r["process_correct_predicted"])
        for r in answer_correct_rows
    )
    return BenchmarkReport(total=len(selected), completed=len(completed), api_failures=failures,
        final_answer_accuracy=sum(r.final_answer.status == "valid" for r in completed) / len(completed) if completed else 0.0,
        process_accuracy=sum(r.process_correct for r in completed) / len(completed) if completed else 0.0,
        deterministic_error_rate=invalid_steps / len(completed) if completed else 0.0,
        uncertain_process_rate=uncertain_steps / len(completed) if completed else 0.0,
        answer_correct_process_invalid_rate=sum(r.answer_correct_but_process_invalid for r in completed) / len(completed) if completed else 0.0,
        by_difficulty=benchmark_by_difficulty,
        by_category=_group_metrics(completed, problem_map, "category") if completed else {},
        error_type_distribution=dict(errors), results=results,
        validation_total=len(validation_rows),
        validation_process_issue_detection_rate=sum(bool(r["first_error_detected"]) for r in wrong_rows) / len(wrong_rows) if wrong_rows else None,
        validation_first_error_detection_rate=wrong_answer_detected / len(wrong_rows) if wrong_rows else None,
        validation_first_error_localization_accuracy=wrong_answer_localized / len(wrong_rows) if wrong_rows else None,
        # “误报率” uses all validation samples with a correct final answer as
        # denominator.  This is the requested operating definition: clean
        # correct samples plus correct-answer/wrong-process samples.
        validation_false_positive_rate=answer_correct_false_positive / len(answer_correct_rows) if answer_correct_rows else None,
        validation_wrong_answer_total=len(wrong_rows),
        validation_wrong_answer_detected_count=wrong_answer_detected,
        validation_wrong_answer_localized_count=wrong_answer_localized,
        validation_correct_total=len(correct_rows),
        validation_correct_flagged_count=correct_flagged,
        validation_correct_true_problem_count=correct_true_problem,
        validation_false_positive_count=false_positive,
        validation_false_positive_share=false_positive / correct_flagged if correct_flagged else None,
        validation_answer_correct_total=len(answer_correct_rows),
        validation_answer_correct_flagged_count=answer_correct_flagged,
        validation_answer_correct_true_problem_count=answer_correct_true_problem,
        validation_answer_correct_false_positive_count=answer_correct_false_positive,
        validation_answer_correct_precision=(
            (answer_correct_flagged - answer_correct_false_positive) / answer_correct_flagged
            if answer_correct_flagged else None
        ),
        validation_answer_correct_false_positive_rate=(
            answer_correct_false_positive / len(answer_correct_rows)
            if answer_correct_rows else None
        ),
        validation_answer_correct_false_positive_share=(
            answer_correct_false_positive / answer_correct_flagged
            if answer_correct_flagged else None
        ),
        validation_true_problem_rate=(sum(r["human_review"] == "真实问题" for r in validation_rows) / len(validation_rows)) if validation_rows else None,
        validation_answer_correct_process_invalid_rate=sum(bool(r["answer_correct_but_process_invalid"]) for r in invalid_answer_process_rows) / len(invalid_answer_process_rows) if invalid_answer_process_rows else None,
        validation_by_kind=validation_by_kind,
        validation_by_difficulty=validation_by_difficulty,
        validation_error_type_distribution=validation_error_distribution,
        validation_results=validation_rows,
        performance_decline_layer=_performance_decline_layer(benchmark_by_difficulty))
