from hy3_eval.formula_renderer import render_formula


def test_power_and_root_rendering():
    power = render_formula("x**2")
    assert power.parse_status == "parsed"
    assert "x^{2}" in power.latex
    assert "x²" in power.unicode

    fraction = render_formula("1/(2*sqrt(x))")
    assert fraction.parse_status == "parsed"
    assert "sqrt" in fraction.latex
    assert "/" in fraction.unicode


def test_integral_and_infinity_rendering():
    result = render_formula("Integral(exp(-x), (x, 0, oo))")
    assert result.parse_status == "parsed"
    assert "int" in result.latex
    assert "∞" in result.unicode


def test_assignment_chain_and_provided_latex():
    result = render_formula(r"u = ln(x), dv = dx \\Rightarrow du = (1/x)dx, v = x")
    assert result.parse_status == "parsed"
    assert "u =" in result.latex
    assert "v =" in result.latex

    provided = render_formula("x**2", r"\frac{1}{2}", "1/2")
    assert provided.latex == r"\frac{1}{2}"
    assert provided.unicode == "1/2"


def test_invalid_expression_falls_back_without_raising():
    result = render_formula("this is not a safe expression")
    assert result.parse_status == "fallback"
    assert result.latex is None
    assert result.unicode == "this is not a safe expression"
