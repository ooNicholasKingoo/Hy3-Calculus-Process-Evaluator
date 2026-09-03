from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from sympy.printing.latex import latex as sympy_latex

from .safe_math import parse_expr


@dataclass(frozen=True)
class FormulaDisplay:
    """Presentation-only representation of a mathematical expression."""

    raw: str
    latex: str | None
    unicode: str
    parse_status: Literal["parsed", "fallback"]


_UNICODE_REPLACEMENTS = {
    "\\infty": "∞",
    "\\rightarrow": "→",
    "\\to": "→",
    "\\Rightarrow": "⇒",
    "\\Leftrightarrow": "⇔",
    "\\leq": "≤",
    "\\geq": "≥",
    "\\neq": "≠",
    "\\pm": "±",
    "\\partial": "∂",
    "\\int": "∫",
    "\\sum": "∑",
    "\\prod": "∏",
    "\\sqrt": "√",
    "\\alpha": "α",
    "\\beta": "β",
    "\\gamma": "γ",
    "\\delta": "δ",
    "\\theta": "θ",
    "\\lambda": "λ",
    "\\mu": "μ",
    "\\pi": "π",
    "\\sigma": "σ",
    "\\phi": "φ",
    "\\omega": "ω",
    "\\cdot": "·",
    "\\,": " ",
}
_SUPERSCRIPT = str.maketrans("0123456789+-=()n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿ")


def _normalise_latex(value: str) -> str:
    value = value.strip()
    if value.startswith("$$") and value.endswith("$$"):
        value = value[2:-2].strip()
    elif value.startswith("$") and value.endswith("$"):
        value = value[1:-1].strip()
    return value


def _latex_to_unicode(value: str) -> str:
    text = _normalise_latex(value)
    # Simplify layout commands before replacing symbols so braces are not
    # left behind in the plain-text representation.
    # Replace one or more balanced ``\frac{...}{...}`` blocks.  A small
    # scanner handles nested braces such as ``\frac{1}{2\sqrt{x}}`` better
    # than a regular expression alone.
    while "\\frac" in text:
        start = text.find("\\frac")
        cursor = start + len("\\frac")
        groups: list[str] = []
        for _ in range(2):
            while cursor < len(text) and text[cursor].isspace():
                cursor += 1
            if cursor >= len(text) or text[cursor] != "{":
                break
            depth, end = 0, cursor
            for end in range(cursor, len(text)):
                if text[end] == "{":
                    depth += 1
                elif text[end] == "}":
                    depth -= 1
                    if depth == 0:
                        break
            if depth != 0:
                break
            groups.append(text[cursor + 1:end])
            cursor = end + 1
        if len(groups) != 2:
            break
        text = text[:start] + f"({groups[0]})/({groups[1]})" + text[cursor:]
    text = re.sub(r"\\sqrt\{([^{}]+)\}", r"√(\1)", text)
    for source, target in sorted(_UNICODE_REPLACEMENTS.items(), key=lambda item: -len(item[0])):
        text = text.replace(source, target)
    text = re.sub(r"\\(?:ln|log|sin|cos|tan|cot|sec|csc|exp)\b", lambda m: m.group(0)[1:], text)
    text = text.replace(r"\!", "")
    text = text.replace(r"\quad", "  ")
    text = re.sub(r"\\limits", "", text)
    text = re.sub(r"\^\{([^{}]+)\}", lambda m: m.group(1).translate(_SUPERSCRIPT), text)
    text = text.replace("^", "^")
    text = re.sub(r"_\{([^{}]+)\}", r"_(\1)", text)
    text = text.replace("\\left", "").replace("\\right", "")
    text = re.sub(r"\\([{}])", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _split_math_chain(raw: str) -> list[str]:
    """Split common prose-free chains while preserving LaTeX commands."""
    pieces = [part.strip() for part in re.split(r"\s*(?:;|\n|⇒|→|\\Rightarrow|\\to)\s*", raw) if part.strip()]
    return pieces or [raw.strip()]


def _text_to_latex(text: str) -> str:
    """Escape a short notation fragment when it is not a SymPy expression."""
    value = text.strip().replace("&", r"\&").replace("%", r"\%").replace("#", r"\#")
    value = value.replace("→", r"\to ").replace("⇒", r"\Rightarrow ")
    value = value.replace("∞", r"\infty ").replace("π", r"\pi ")
    return value


def _render_piece(piece: str, variable: str) -> str:
    """Render an expression or a short assignment without losing its lhs."""
    # Commas separate short assignments in common calculus working, e.g.
    # ``u=ln(x), dv=dx``. Split only at top-level commas.
    parts: list[str] = []
    depth = 0
    start = 0
    for index, char in enumerate(piece):
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            parts.append(piece[start:index].strip())
            start = index + 1
    parts.append(piece[start:].strip())
    rendered: list[str] = []
    for item in (part for part in parts if part):
        differential = re.fullmatch(r"d([A-Za-z])", item.replace(" ", ""))
        if differential:
            rendered.append(rf"d{differential.group(1)}")
            continue
        original_item = item
        item = re.sub(r"\)(d[A-Za-z])\b", r") \\!\1", item)
        if "=" in item and not item.lstrip().startswith(("<", ">", "=")):
            lhs, rhs = item.split("=", 1)
            lhs = lhs.strip()
            rhs = rhs.strip()
            if re.fullmatch(r"(?:\([^)]*\)|[A-Za-z0-9_/*+(). -]+)d[A-Za-z]", original_item.split("=", 1)[1].strip()):
                rhs_latex = _text_to_latex(rhs).replace("*", r" \\!")
                rendered.append(f"{lhs} = {rhs_latex}")
                continue
            try:
                rhs_latex = _parse_to_latex(rhs, variable)
                rendered.append(f"{lhs} = {rhs_latex}")
                continue
            except Exception:
                rendered.append(_text_to_latex(item))
                continue
        try:
            rendered.append(_parse_to_latex(item, variable))
        except Exception:
            rendered.append(_text_to_latex(item))
    return r",\quad ".join(rendered)


def _parse_to_latex(raw: str, variable: str) -> str:
    # parse_expr applies the project's restricted SymPy parsing policy.
    expr = parse_expr(raw, variable)
    return sympy_latex(expr, fold_short_frac=False, mode="plain")


def render_formula(
    raw: str | None,
    provided_latex: str | None = None,
    provided_unicode: str | None = None,
    variable: str = "x",
) -> FormulaDisplay:
    raw_text = str(raw or "").strip()
    if provided_latex and provided_latex.strip():
        latex_text = _normalise_latex(provided_latex)
        return FormulaDisplay(raw_text, latex_text, provided_unicode.strip() if provided_unicode else _latex_to_unicode(latex_text), "parsed")
    if not raw_text:
        return FormulaDisplay(raw_text, None, provided_unicode.strip() if provided_unicode else "", "fallback")
    try:
        # Hy3 sometimes returns a complete chain such as "u=..., dv=...".
        pieces = _split_math_chain(raw_text)
        rendered: list[str] = []
        for piece in pieces:
            try:
                rendered.append(_render_piece(piece, variable))
            except Exception:
                rendered.append(piece)
        if not rendered or all(piece == raw_text for piece in rendered):
            raise ValueError("expression could not be parsed")
        latex_text = r" \\; ".join(rendered)
        return FormulaDisplay(raw_text, latex_text, provided_unicode.strip() if provided_unicode else _latex_to_unicode(latex_text), "parsed")
    except Exception:
        return FormulaDisplay(raw_text, None, provided_unicode.strip() if provided_unicode else raw_text, "fallback")


def render_step_formulas(step, variable: str = "x") -> tuple[FormulaDisplay, FormulaDisplay]:
    return (
        render_formula(step.expression_before, step.latex_before, step.unicode_before, variable),
        render_formula(step.expression_after, step.latex_after, step.unicode_after, variable),
    )
