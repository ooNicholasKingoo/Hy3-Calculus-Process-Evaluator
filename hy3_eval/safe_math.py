from __future__ import annotations
import re
import sympy as sp

_ALLOWED = {"sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "exp": sp.exp, "log": sp.log,
            "sqrt": sp.sqrt, "pi": sp.pi, "E": sp.E, "oo": sp.oo, "Abs": sp.Abs,
            "asin": sp.asin, "acos": sp.acos, "atan": sp.atan}

def parse_expr(text: str, variable: str = "x") -> sp.Expr:
    if not text or len(text) > 500:
        raise ValueError("expression is empty or too long")
    if re.search(r"(__|import|lambda|exec|eval|open|system)", text, re.I):
        raise ValueError("unsafe expression")
    symbol = sp.Symbol(variable, real=True)
    local = dict(_ALLOWED)
    local[variable] = symbol
    # A few advanced exercises use a parameter or an implicit-function symbol.
    # They are parsed as real symbols, never evaluated as Python code.
    for name in ("x", "y", "t", "p"):
        local.setdefault(name, sp.Symbol(name, real=True))
    return sp.sympify(text.replace("^", "**"), locals=local, evaluate=True)

def equivalent(a: sp.Expr, b: sp.Expr) -> bool:
    try:
        return bool(sp.simplify(a - b) == 0)
    except Exception:
        try:
            return bool(sp.trigsimp(a - b) == 0)
        except Exception:
            return False
