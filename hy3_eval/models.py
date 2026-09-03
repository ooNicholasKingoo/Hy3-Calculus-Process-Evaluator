from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field

Category = Literal["limit", "derivative", "integral"]
Difficulty = Literal["basic", "intermediate", "advanced"]
CheckStatus = Literal["valid", "invalid", "uncertain"]
ErrorCode = Literal[
    "question_misread", "concept_error", "calculation_error", "condition_omission",
    "jumped_derivation", "format_error", "logical_error", "guessed_option", "numerical_coincidence",
    "theorem_misuse_correct_result", "test_case_coincidence", "circular_reasoning",
    "domain_convergence_omission", "unsupported_claim",
]

ERROR_TYPE_LABELS: dict[str, str] = {
    "question_misread": "题意误读",
    "concept_error": "概念理解错误",
    "calculation_error": "计算错误",
    "condition_omission": "条件遗漏",
    "jumped_derivation": "跳步推导",
    "format_error": "格式不符",
    "logical_error": "逻辑推理错误",
    "guessed_option": "猜中选项",
    "numerical_coincidence": "数值巧合",
    "theorem_misuse_correct_result": "误用定理但得出正确结果",
    "test_case_coincidence": "恰好通过测试用例但实现逻辑存在缺陷",
    "circular_reasoning": "循环论证",
    "domain_convergence_omission": "定义域或收敛条件遗漏",
    "unsupported_claim": "无依据结论",
}

def error_type_label(value: str | None) -> str | None:
    """Return the stable Chinese label while allowing legacy labels through."""
    if not value:
        return None
    return ERROR_TYPE_LABELS.get(value, value)
ConnectionStatus = Literal["ok", "failed"]
ConnectionKind = Literal[
    "authentication", "permission", "network", "timeout", "rate_limit",
    "bad_request", "model_not_found", "server_error", "response_parse", "unknown",
]

class ConnectionDiagnostic(BaseModel):
    status: ConnectionStatus
    kind: ConnectionKind
    message: str
    endpoint: str
    model: str
    elapsed_ms: int = 0
    retry_count: int = 0
    request_id: str | None = None
    hint: str | None = None

class ReferenceStep(BaseModel):
    number: int
    description: str
    expression_before: str | None = None
    expression_after: str | None = None
    theorem: str | None = None
    condition: str | None = None

class CalculusProblem(BaseModel):
    id: str
    category: Category
    difficulty: Difficulty
    prompt: str
    expression: str
    variable: str = "x"
    point: str | None = None
    lower: str | None = None
    upper: str | None = None
    answer_type: Literal["limit", "derivative", "antiderivative", "definite_integral"]
    standard_answer: str
    answer_mode: Literal["expression", "text"] = "expression"
    derivative_order: int = 1
    metadata: dict[str, str] = Field(default_factory=dict)
    reference_steps: list[ReferenceStep] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    source: str = "大学真题"
    construction: str = "由公开课程知识点参数化构造"

    @property
    def minimum_steps(self) -> int:
        """Recommended minimum for process-quality checks, not a proof rule."""
        value = self.metadata.get("minimum_steps")
        try:
            return max(1, int(value)) if value is not None else (5 if self.difficulty == "advanced" else 3)
        except (TypeError, ValueError):
            return 5 if self.difficulty == "advanced" else 3

class SolutionStep(BaseModel):
    number: int
    expression_before: str | None = None
    expression_after: str | None = None
    # Optional presentation fields supplied by Hy3.  Validation always uses
    # the raw expression fields above; these fields are display-only.
    latex_before: str | None = None
    latex_after: str | None = None
    unicode_before: str | None = None
    unicode_after: str | None = None
    theorem: str | None = None
    condition: str | None = None
    explanation: str = ""

class CandidateSolution(BaseModel):
    problem_id: str
    category: Category
    final_answer: str
    steps: list[SolutionStep] = Field(default_factory=list)
    method_summary: str = ""
    assumptions: list[str] = Field(default_factory=list)
    raw_text: str = ""
    parse_error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

class FinalAnswerCheck(BaseModel):
    status: CheckStatus
    expected: str
    actual: str
    evidence: str
    expected_latex: str | None = None
    actual_latex: str | None = None
    expected_unicode: str | None = None
    actual_unicode: str | None = None
    formula_parse_status: Literal["parsed", "fallback"] | None = None


class RuleCheck(BaseModel):
    code: str
    status: CheckStatus
    message: str
    evidence: str = ""


class LLMJudgeResult(BaseModel):
    status: Literal["verified", "invalid", "needs_review"] = "needs_review"
    is_correct: bool | None = None
    error_step_index: int = -1
    error_type: str | None = None
    is_lucky_guess: bool = False
    explanation: str = ""
    raw_response: str = ""

class ProcessIssue(BaseModel):
    """A separately auditable finding attached to one solution step."""
    step_number: int
    status: CheckStatus
    error_type: str | None = None
    code: str
    evidence: str
    affected: bool = False

class ProcessSummary(BaseModel):
    status: Literal["verified", "invalid", "needs_review"]
    first_error_step: int | None = None
    first_review_step: int | None = None
    primary_error_type: str | None = None
    error_types: list[str] = Field(default_factory=list)
    explanation: str = ""

class StepAssessment(BaseModel):
    number: int
    status: CheckStatus
    error_type: str | None = None
    evidence: str = ""
    affected: bool = False
    llm_review: str | None = None
    issues: list[ProcessIssue] = Field(default_factory=list)
    latex_before: str | None = None
    latex_after: str | None = None
    unicode_before: str | None = None
    unicode_after: str | None = None
    formula_parse_status: Literal["parsed", "fallback"] | None = None

class EvaluationResult(BaseModel):
    problem_id: str
    final_answer: FinalAnswerCheck
    steps: list[StepAssessment] = Field(default_factory=list)
    process_correct: bool
    first_error_step: int | None = None
    first_review_step: int | None = None
    review_status: Literal["verified", "invalid", "needs_review"] = "needs_review"
    error_types: list[str] = Field(default_factory=list)
    answer_correct_but_process_invalid: bool = False
    process_summary: ProcessSummary | None = None
    api_failed: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    rule_checks: list[RuleCheck] = Field(default_factory=list)
    llm_judge: LLMJudgeResult | None = None

class BenchmarkReport(BaseModel):
    total: int
    completed: int
    api_failures: int
    final_answer_accuracy: float
    process_accuracy: float
    deterministic_error_rate: float = 0.0
    uncertain_process_rate: float = 0.0
    answer_correct_process_invalid_rate: float = 0.0
    first_error_detection_rate: float | None = None
    first_error_localization_accuracy: float | None = None
    by_difficulty: dict[str, dict[str, float]] = Field(default_factory=dict)
    by_category: dict[str, dict[str, float]] = Field(default_factory=dict)
    error_type_distribution: dict[str, int] = Field(default_factory=dict)
    results: list[EvaluationResult] = Field(default_factory=list)
    # Validation against hand-labelled synthetic samples. These fields are
    # separate from the model benchmark so API failures never distort the
    # evaluator's validity metrics.
    validation_total: int = 0
    validation_process_issue_detection_rate: float | None = None
    validation_first_error_detection_rate: float | None = None
    validation_first_error_localization_accuracy: float | None = None
    validation_false_positive_rate: float | None = None
    # Explicit denominators/counts make the validity report auditable instead
    # of presenting an unexplained percentage.
    validation_wrong_answer_total: int = 0
    validation_wrong_answer_detected_count: int = 0
    validation_wrong_answer_localized_count: int = 0
    validation_correct_total: int = 0
    validation_correct_flagged_count: int = 0
    validation_correct_true_problem_count: int = 0
    validation_false_positive_count: int = 0
    validation_false_positive_share: float | None = None
    # Metrics over every sample whose final answer is correct (clean and
    # correct-answer/wrong-process cohorts), with human review as reference.
    validation_answer_correct_total: int = 0
    validation_answer_correct_flagged_count: int = 0
    validation_answer_correct_true_problem_count: int = 0
    validation_answer_correct_false_positive_count: int = 0
    validation_answer_correct_precision: float | None = None
    validation_answer_correct_false_positive_rate: float | None = None
    validation_answer_correct_false_positive_share: float | None = None
    validation_true_problem_rate: float | None = None
    validation_answer_correct_process_invalid_rate: float | None = None
    validation_by_kind: dict[str, dict[str, float]] = Field(default_factory=dict)
    validation_by_difficulty: dict[str, dict[str, float]] = Field(default_factory=dict)
    validation_error_type_distribution: dict[str, int] = Field(default_factory=dict)
    validation_results: list[dict[str, Any]] = Field(default_factory=list)
    performance_decline_layer: str | None = None
