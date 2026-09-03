from __future__ import annotations
from dataclasses import dataclass
import sympy as sp
from .models import CalculusProblem, CandidateSolution, FinalAnswerCheck, SolutionStep, StepAssessment
from .safe_math import equivalent, parse_expr

@dataclass
class ValidationEvidence:
    status: str
    evidence: str
    error_type: str | None = None
    code: str = "unverified"

def _answer_expr(text: str, variable: str) -> sp.Expr:
    return parse_expr(text.strip().split("=")[-1].strip(), variable)

def validate_final_answer(problem: CalculusProblem, solution: CandidateSolution) -> FinalAnswerCheck:
    expected = problem.standard_answer
    if solution.parse_error:
        return FinalAnswerCheck(status="uncertain", expected=expected, actual=solution.final_answer,
                                evidence=f"候选解 JSON 无法解析，未对最终答案作出数学判定：{solution.parse_error}")
    if problem.answer_mode == "text":
        actual = solution.final_answer.strip().replace(" ", "")
        target = expected.strip().replace(" ", "")
        if actual == target or target in actual:
            return FinalAnswerCheck(status="valid", expected=expected, actual=solution.final_answer, evidence="文字型标准答案匹配")
        return FinalAnswerCheck(status="invalid", expected=expected, actual=solution.final_answer, evidence="文字型标准答案不匹配")
    try:
        actual = _answer_expr(solution.final_answer, problem.variable)
        target = _answer_expr(expected, problem.variable)
        if equivalent(actual, target):
            return FinalAnswerCheck(status="valid", expected=expected, actual=solution.final_answer, evidence="符号化简后与标准答案等价")
    except Exception:
        pass
    return FinalAnswerCheck(status="invalid", expected=expected, actual=solution.final_answer, evidence="无法证明候选答案与标准答案等价")

def _transition(problem: CalculusProblem, step: SolutionStep) -> ValidationEvidence:
    if problem.answer_mode == "text":
        return ValidationEvidence("valid", "该题结论属于定义/性质判断，由最终结论与条件说明共同核验")
    special = problem.metadata.get("special_validation")
    if special in {"implicit", "parameter"}:
        expected_text = problem.metadata.get("expected_step", problem.standard_answer)
        try:
            actual = _answer_expr(step.expression_after or "", problem.variable)
            expected = _answer_expr(expected_text, problem.variable)
            if equivalent(actual, expected):
                rule = "隐函数求导公式" if special == "implicit" else "参数方程 dy/dx=(dy/dt)/(dx/dt)"
                return ValidationEvidence("valid", f"{rule}与标准结果一致", code="symbolic_match")
            return ValidationEvidence("invalid", f"特殊题型步骤结果应为 {expected_text}，实际为 {step.expression_after}", "代数/微积分计算错误", "calculation_error")
        except Exception as exc:
            return ValidationEvidence("uncertain", f"特殊题型步骤的数学关系暂无法自动验证（底层解析信息：{type(exc).__name__}: {exc}）。请人工复核。", None, "expression_parse_uncertain")
    if not step.expression_before or not step.expression_after:
        return ValidationEvidence("uncertain", "缺少可比较的前后表达式，无法证明这一步成立", "无依据跳步", "jumped_derivation")
    try:
        before = parse_expr(step.expression_before, problem.variable)
        after = parse_expr(step.expression_after, problem.variable)
        var = sp.Symbol(problem.variable, real=True)
        if problem.category == "derivative":
            expected = sp.diff(before, var, problem.derivative_order)
            if equivalent(expected, after):
                return ValidationEvidence("valid", "导数恒等式验证通过", code="derivative_identity")
            return ValidationEvidence("invalid", f"{problem.derivative_order} 阶导数期望为 {sp.sstr(expected)}，实际为 {sp.sstr(after)}", "代数/微积分计算错误", "calculation_error")
        if problem.category == "integral":
            if equivalent(sp.diff(after, var), before):
                return ValidationEvidence("valid", "对结果求导后恢复原被积函数", code="integral_backcheck")
            if equivalent(before, after):
                return ValidationEvidence("valid", "表达式保持等价", code="equivalent_expression")
            return ValidationEvidence("invalid", "积分步骤未能通过求导回代验证", "代数/微积分计算错误", "calculation_error")
        if problem.category == "limit":
            if equivalent(before, after):
                return ValidationEvidence("valid", "极限内表达式变形保持恒等", code="equivalent_expression")
            point = parse_expr(problem.point or "0", problem.variable)
            left = sp.limit(before, var, point, dir="-")
            right = sp.limit(before, var, point, dir="+")
            target = sp.limit(after, var, point)
            if left == right and (target == left or equivalent(target, left)):
                return ValidationEvidence("valid", "左右极限与变形结果一致", code="limit_backcheck")
            if left == right and target != left:
                return ValidationEvidence("invalid", f"原表达式极限为 {sp.sstr(left)}，本步得到 {sp.sstr(target)}，结论不成立", "代数/微积分计算错误", "calculation_error")
            return ValidationEvidence("uncertain", "极限变形无法仅凭局部符号关系确认，需要人工复核", "定理使用条件遗漏", "limit_relation_uncertain")
    except Exception as exc:
        return ValidationEvidence("uncertain", f"本步数学关系暂无法自动验证（底层解析信息：{type(exc).__name__}: {exc}）。请结合题意和推导说明人工复核。", None, "expression_parse_uncertain")
    return ValidationEvidence("uncertain", "没有适用的确定性规则，需要人工复核", code="no_deterministic_rule")

def validate_step(problem: CalculusProblem, step: SolutionStep) -> StepAssessment:
    result = _transition(problem, step)
    return StepAssessment(number=step.number, status=result.status, error_type=result.error_type, evidence=result.evidence)

def assess_conditions(problem: CalculusProblem, step: SolutionStep) -> ValidationEvidence:
    theorem = (step.theorem or "").lower()
    condition = (step.condition or "").strip()
    if any(word in theorem for word in ("洛必达", "l'hopital", "l'hôpital", "泰勒", "换元", "分部积分")) and not condition:
        return ValidationEvidence("uncertain", "使用了需要前提条件的定理，但未说明条件", "定理使用条件遗漏", "theorem_condition_missing")
    if problem.category == "integral" and "反常" in problem.tags and not condition:
        return ValidationEvidence("uncertain", "反常积分未说明收敛性或端点条件", "定义域或收敛条件遗漏", "domain_convergence_missing")
    return ValidationEvidence("valid", "未发现明显的条件说明缺失", code="conditions_present")
