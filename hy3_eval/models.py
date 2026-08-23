from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field

Category = Literal["limit", "derivative", "integral"]
Difficulty = Literal["basic", "intermediate", "advanced"]
CheckStatus = Literal["valid", "invalid", "uncertain"]

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
    reference_steps: list[ReferenceStep] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    source: str = "原创/程序化构造"
    construction: str = "由公开课程知识点参数化构造"

class SolutionStep(BaseModel):
    number: int
    expression_before: str | None = None
    expression_after: str | None = None
    theorem: str | None = None
    condition: str | None = None
    explanation: str = ""

class CandidateSolution(BaseModel):
    problem_id: str
    category: Category
    final_answer: str
    steps: list[SolutionStep] = Field(default_factory=list)
    raw_text: str = ""
    parse_error: str | None = None

class FinalAnswerCheck(BaseModel):
    status: CheckStatus
    expected: str
    actual: str
    evidence: str

class StepAssessment(BaseModel):
    number: int
    status: CheckStatus
    error_type: str | None = None
    evidence: str = ""
    affected: bool = False
    llm_review: str | None = None

class EvaluationResult(BaseModel):
    problem_id: str
    final_answer: FinalAnswerCheck
    steps: list[StepAssessment] = Field(default_factory=list)
    process_correct: bool
    first_error_step: int | None = None
    error_types: list[str] = Field(default_factory=list)
    answer_correct_but_process_invalid: bool = False
    api_failed: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

class BenchmarkReport(BaseModel):
    total: int
    completed: int
    api_failures: int
    final_answer_accuracy: float
    process_accuracy: float
    first_error_detection_rate: float | None = None
    first_error_localization_accuracy: float | None = None
    by_difficulty: dict[str, dict[str, float]] = Field(default_factory=dict)
    by_category: dict[str, dict[str, float]] = Field(default_factory=dict)
    error_type_distribution: dict[str, int] = Field(default_factory=dict)
    results: list[EvaluationResult] = Field(default_factory=list)
