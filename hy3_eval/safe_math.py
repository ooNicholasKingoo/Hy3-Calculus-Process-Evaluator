from __future__ import annotations
import re
import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor, implicit_multiplication_application, parse_expr as sympy_parse_expr,
    standard_transformations,
)

_ALLOWED = {"sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "exp": sp.exp, "log": sp.log,
            "sqrt": sp.sqrt, "pi": sp.pi, "E": sp.E, "oo": sp.oo, "Abs": sp.Abs,
            "asin": sp.asin, "acos": sp.acos, "atan": sp.atan}

def parse_expr(text: str, variable: str = "x") -> sp.Expr:
    if not text or len(text) > 500:
        raise ValueError("expression is empty or too long")
    if re.search(r"(__|import|lambda|exec|eval|open|system)", text, re.I):
        raise ValueError("unsafe expression")
    text = _normalize_math_text(text)
    symbol = sp.Symbol(variable, real=True)
    local = dict(_ALLOWED)
    local[variable] = symbol
    # A few advanced exercises use a parameter or an implicit-function symbol.
    # They are parsed as real symbols, never evaluated as Python code.
    for name in ("x", "y", "t", "p"):
        local.setdefault(name, sp.Symbol(name, real=True))
    transformations = standard_transformations + (convert_xor, implicit_multiplication_application)
    return sympy_parse_expr(text, local_dict=local, transformations=transformations, evaluate=True)


def _normalize_math_text(text: str) -> str:
    """Accept common model LaTeX/Unicode notation without executing code."""
    value = str(text).strip()
    value = value.replace("−", "-").replace("×", "*").replace("·", "*")
    value = value.replace("∞", "oo").replace("π", "pi")
    value = value.replace("\\left", "").replace("\\right", "")
    value = value.replace("\\cdot", "*").replace("\\times", "*")
    value = re.sub(r"\\(sin|cos|tan|log|exp|sqrt|arcsin|arccos|arctan)\b", r"\1", value)
    value = value.replace("\\pi", "pi").replace("\\infty", "oo")
    value = value.replace("\\,", " ").replace("\\!", "")
    # Handle the common one-level LaTeX fraction and root forms.
    for _ in range(4):
        old = value
        value = re.sub(r"\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"(\1)/(\2)", value)
        value = re.sub(r"\\sqrt\s*\{([^{}]*)\}", r"sqrt(\1)", value)
        if value == old: break
    value = value.replace("\\", "")
    value = value.replace("{", "(").replace("}", ")")
    value = re.sub(r"\$+|\\\(|\\\)", "", value)
    # Strip labels such as f'(x)= and a leading prose arrow.
    value = re.sub(r"^[^=]{0,30}=", "", value) if "=" in value else value
    value = re.sub(r"^(?:therefore|所以|故|于是|答案|最终答案|result|answer)\s*[:：=]?\s*", "", value, flags=re.I)
    value = value.strip(" 。；;，,。")
    return value.strip()

def equivalent(a: sp.Expr, b: sp.Expr) -> bool:
    try:
        return bool(sp.simplify(a - b) == 0)
    except Exception:
        try:
            return bool(sp.trigsimp(a - b) == 0)
        except Exception:
            return False
