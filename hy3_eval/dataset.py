from __future__ import annotations

import json
from pathlib import Path

import sympy as sp

from .models import CalculusProblem, ReferenceStep


def _p(pid: str, category: str, difficulty: str, prompt: str, expression: str,
       answer_type: str, answer: str, *, point: str | None = None,
       lower: str | None = None, upper: str | None = None, tags: list[str] | None = None,
       steps: list[ReferenceStep] | None = None) -> CalculusProblem:
    return CalculusProblem(id=pid, category=category, difficulty=difficulty, prompt=prompt,
                           expression=expression, point=point, lower=lower, upper=upper,
                           answer_type=answer_type, standard_answer=answer, tags=tags or [],
                           reference_steps=steps or [])


def build_problems() -> list[CalculusProblem]:
    """Create 60 deterministic, original calculus exercises (20 per level)."""
    out: list[CalculusProblem] = []
    # 20 basic: 7 limits, 7 derivatives, 6 integrals.
    basic = [
        ("limit", "计算 lim_{x→0} sin(x)/x", "sin(x)/x", "1", "0", ["基本极限"]),
        ("limit", "计算 lim_{x→0} (1-cos(x))/x^2", "(1-cos(x))/x**2", "1/2", "0", ["基本极限"]),
        ("limit", "计算 lim_{x→2} (x^2-4)/(x-2)", "(x**2-4)/(x-2)", "4", "2", ["因式分解"]),
        ("limit", "计算 lim_{x→∞} (3*x^2+1)/(x^2-2)", "(3*x**2+1)/(x**2-2)", "3", "oo", ["无穷极限"]),
        ("limit", "计算 lim_{x→0} (exp(x)-1)/x", "(exp(x)-1)/x", "1", "0", ["指数极限"]),
        ("limit", "计算 lim_{x→1} log(x)/(x-1)", "log(x)/(x-1)", "1", "1", ["对数极限"]),
        ("limit", "计算 lim_{x→0} (sqrt(1+x)-1)/x", "(sqrt(1+x)-1)/x", "1/2", "0", ["有理化"]),
        ("derivative", "求 f(x)=x^3-2x+1 的导数", "x**3-2*x+1", "3*x**2-2", None, ["基本求导"]),
        ("derivative", "求 f(x)=sin(x)+exp(x) 的导数", "sin(x)+exp(x)", "cos(x)+exp(x)", None, ["基本求导"]),
        ("derivative", "求 f(x)=log(x) 的导数", "log(x)", "1/x", None, ["对数函数"]),
        ("derivative", "求 f(x)=sqrt(x) 的导数", "sqrt(x)", "1/(2*sqrt(x))", None, ["幂函数"]),
        ("derivative", "求 f(x)=x*sin(x) 的导数", "x*sin(x)", "sin(x)+x*cos(x)", None, ["乘积法则"]),
        ("derivative", "求 f(x)=sin(x^2) 的导数", "sin(x**2)", "2*x*cos(x**2)", None, ["链式法则"]),
        ("derivative", "求 f(x)=1/(x+1) 的导数", "1/(x+1)", "-1/(x+1)**2", None, ["基本求导"]),
        ("integral", "求 ∫(3x^2-4x+1)dx", "3*x**2-4*x+1", "x**3-2*x**2+x", None, ["基本积分"]),
        ("integral", "求 ∫cos(x)dx", "cos(x)", "sin(x)", None, ["基本积分"]),
        ("integral", "求 ∫exp(x)dx", "exp(x)", "exp(x)", None, ["基本积分"]),
        ("integral", "求 ∫1/x dx", "1/x", "log(x)", None, ["对数积分"]),
        ("integral", "计算 ∫_0^1 x^2 dx", "x**2", "1/3", None, ["定积分"]),
        ("integral", "计算 ∫_0^pi sin(x)dx", "sin(x)", "2", None, ["定积分"]),
    ]
    for i, (cat, prompt, expr, ans, point, tags) in enumerate(basic, 1):
        if cat == "integral" and i >= 19:
            lo, hi = ("0", "1") if i == 19 else ("0", "pi")
            out.append(_p(f"B-{i:02d}", cat, "basic", prompt, expr, "definite_integral", ans, lower=lo, upper=hi, tags=tags))
        else:
            typ = "limit" if cat == "limit" else "derivative" if cat == "derivative" else "antiderivative"
            out.append(_p(f"B-{i:02d}", cat, "basic", prompt, expr, typ, ans, point=point, tags=tags))

    intermediate = [
        ("limit", "lim_{x→0} (tan(x)-x)/x^3", "(tan(x)-x)/x**3", "1/3", "0", ["泰勒展开"]),
        ("limit", "lim_{x→0} (exp(x)-1-x)/x^2", "(exp(x)-1-x)/x**2", "1/2", "0", ["泰勒展开"]),
        ("limit", "lim_{x→∞} x/(x+exp(-x))", "x/(x+exp(-x))", "1", "oo", ["无穷极限"]),
        ("limit", "lim_{x→0} log(1+x)/x", "log(1+x)/x", "1", "0", ["等价无穷小"]),
        ("limit", "lim_{x→0} (1-cos(2*x))/x^2", "(1-cos(2*x))/x**2", "2", "0", ["等价无穷小"]),
        ("limit", "lim_{x→1} (x**3-1)/(x-1)", "(x**3-1)/(x-1)", "3", "1", ["洛必达"]),
        ("limit", "lim_{x→0} (sqrt(1+x)-1-x/2)/x^2", "(sqrt(1+x)-1-x/2)/x**2", "-1/8", "0", ["泰勒展开"]),
        ("derivative", "求 y=(x^2+1)^5 的导数", "(x**2+1)**5", "10*x*(x**2+1)**4", None, ["链式法则"]),
        ("derivative", "求 y=x^x (x>0) 的导数", "x**x", "x**x*(log(x)+1)", None, ["对数求导"]),
        ("derivative", "求 y=arctan(x^2) 的导数", "atan(x**2)", "2*x/(1+x**4)", None, ["链式法则"]),
        ("derivative", "由 x^2+y^2=1 求 dy/dx", "x**2+y**2", "-x/y", None, ["隐函数求导"]),
        ("derivative", "求 y=(sin x)^x 的导数", "sin(x)**x", "sin(x)**x*(log(sin(x))+x*cos(x)/sin(x))", None, ["对数求导"]),
        ("derivative", "求 y=exp(x)/(1+x) 的导数", "exp(x)/(1+x)", "x*exp(x)/(1+x)**2", None, ["商法则"]),
        ("derivative", "求 y=log(sin x) 的导数", "log(sin(x))", "cos(x)/sin(x)", None, ["链式法则"]),
        ("integral", "用换元法求 ∫2x*cos(x^2)dx", "2*x*cos(x**2)", "sin(x**2)", None, ["换元"]),
        ("integral", "用分部积分求 ∫x*exp(x)dx", "x*exp(x)", "(x-1)*exp(x)", None, ["分部积分"]),
        ("integral", "求 ∫x/(1+x^2)dx", "x/(1+x**2)", "log(1+x**2)/2", None, ["换元"]),
        ("integral", "计算 ∫_0^1 x*log(x)dx", "x*log(x)", "-1/4", None, ["反常积分", "分部积分"]),
        ("integral", "计算 ∫_0^pi x*sin(x)dx", "x*sin(x)", "pi", None, ["分部积分"]),
        ("integral", "计算 ∫_0^1 1/(1+x^2)dx", "1/(1+x**2)", "pi/4", None, ["反三角函数"]),
    ]
    for i, (cat, prompt, expr, ans, point, tags) in enumerate(intermediate, 1):
        typ = "limit" if cat == "limit" else "derivative" if cat == "derivative" else ("definite_integral" if "∫_" in prompt else "antiderivative")
        kwargs = {"point": point, "tags": tags}
        if typ == "definite_integral":
            kwargs.update(lower="0", upper="pi" if "pi" in prompt else "1")
        out.append(_p(f"I-{i:02d}", cat, "intermediate", prompt, expr, typ, ans, **kwargs))

    advanced = [
        ("limit", "lim_{x→0} (1/x - 1/(exp(x)-1))", "1/x-1/(exp(x)-1)", "1/2", "0", ["洛必达", "泰勒展开"]),
        ("limit", "lim_{x→0} (sin(x)-x+x^3/6)/x^5", "(sin(x)-x+x**3/6)/x**5", "1/120", "0", ["高阶泰勒"]),
        ("limit", "lim_{x→∞} x*(sqrt(x^2+1)-x)", "x*(sqrt(x**2+1)-x)", "1/2", "oo", ["有理化"]),
        ("limit", "lim_{x→0} (log(1+x)-x+x^2/2)/x^3", "(log(1+x)-x+x**2/2)/x**3", "1/3", "0", ["高阶泰勒"]),
        ("limit", "lim_{x→0} (1+x)^(1/x)", "(1+x)**(1/x)", "E", "0", ["复合极限"]),
        ("limit", "lim_{x→0} (cos(x))^(1/x^2)", "cos(x)**(1/x**2)", "exp(-1/2)", "0", ["复合极限"]),
        ("limit", "lim_{x→0} (exp(x)-exp(-x)-2*x)/x^3", "(exp(x)-exp(-x)-2*x)/x**3", "1/3", "0", ["高阶泰勒"]),
        ("derivative", "求 y=x^(sin x) (x>0) 的导数", "x**sin(x)", "x**sin(x)*(cos(x)*log(x)+sin(x)/x)", None, ["对数求导"]),
        ("derivative", "由 x*y+sin(y)=1 求 y'", "x*y+sin(y)", "-y/(x+cos(y))", None, ["隐函数求导"]),
        ("derivative", "求 y=log(x^2+sqrt(1+x^4)) 的导数", "log(x**2+sqrt(1+x**4))", "2*x/sqrt(1+x**4)", None, ["复合函数"]),
        ("derivative", "求参数方程 x=t^2+1,y=t^3-t 在 t=1 处 dy/dx", "(t**3-t)/(t**2+1)", "1", None, ["参数方程"]),
        ("derivative", "求 f(x)=|x| 在 x=0 是否可导", "Abs(x)", "0", None, ["不可导点"]),
        ("derivative", "求 y=arcsin(x) 的二阶导数", "asin(x)", "x/(1-x**2)**(3/2)", None, ["高阶导数"]),
        ("derivative", "求 y=x^2*log(x) 的二阶导数", "x**2*log(x)", "2*log(x)+3", None, ["高阶导数"]),
        ("integral", "求 ∫log(x)dx", "log(x)", "x*log(x)-x", None, ["分部积分"]),
        ("integral", "求 ∫x^2*exp(x)dx", "x**2*exp(x)", "(x**2-2*x+2)*exp(x)", None, ["分部积分"]),
        ("integral", "判断 ∫_1^∞ 1/x^p dx 的收敛条件", "x**(-p)", "1/(p-1)", None, ["反常积分", "收敛条件"]),
        ("integral", "计算 ∫_0^∞ exp(-x)dx", "exp(-x)", "1", None, ["反常积分"]),
        ("integral", "计算 ∫_0^1 log(x)/(1+x)dx（可用级数）", "log(x)/(1+x)", "-pi**2/12", None, ["反常积分", "级数"]),
        ("integral", "计算 ∫_0^pi/2 log(sin(x))dx", "log(sin(x))", "-pi*log(2)/2", None, ["反常积分", "参数技巧"]),
    ]
    for i, (cat, prompt, expr, ans, point, tags) in enumerate(advanced, 1):
        typ = "limit" if cat == "limit" else "derivative" if cat == "derivative" else "definite_integral"
        kwargs = {"point": point, "tags": tags}
        if typ == "definite_integral": kwargs.update(lower="0", upper="oo")
        out.append(_p(f"A-{i:02d}", cat, "advanced", prompt, expr, typ, ans, **kwargs))
    return out


def write_dataset(path: str | Path) -> list[CalculusProblem]:
    problems = build_problems()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(json.dumps(p.model_dump(), ensure_ascii=False) for p in problems) + "\n", encoding="utf-8")
    return problems


def load_dataset(path: str | Path) -> list[CalculusProblem]:
    return [CalculusProblem.model_validate(json.loads(line)) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def build_validation_cases(problems: list[CalculusProblem]) -> list[dict]:
    """Create 60 deterministic cases for validating the evaluator itself.

    The cases deliberately include correct answers, wrong answers, and answers
    that are numerically right while the listed process omits a required step.
    Human review fields are explicit so the dataset can be audited later.
    """
    cases: list[dict] = []
    for index, problem in enumerate(problems, 1):
        if index <= 20:
            kind, first_error, types = "correct", None, []
        elif index <= 40:
            kind, first_error, types = "wrong_answer", 1, ["代数/微积分计算错误"]
        else:
            kind, first_error, types = "correct_answer_wrong_process", 1, ["无依据跳步"]
        cases.append({
            "id": f"VC-{index:03d}", "problem_id": problem.id, "kind": kind,
            "expected_first_error_step": first_error, "expected_error_types": types,
            "human_review": "待人工抽检", "difficulty": problem.difficulty,
            "category": problem.category,
        })
    return cases


def write_validation_cases(path: str | Path, problems: list[CalculusProblem] | None = None) -> list[dict]:
    cases = build_validation_cases(problems or build_problems())
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(json.dumps(case, ensure_ascii=False) for case in cases) + "\n", encoding="utf-8")
    return cases
