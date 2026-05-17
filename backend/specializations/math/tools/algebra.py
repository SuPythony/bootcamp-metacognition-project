"""Algebra tool — sympy-backed.

Returns: { result, ui_component: "AlgebraSteps", display_data: { steps, final } }

args:
    expression: str   — the expression or equation (use "=" for solve)
    operation:  str   — "simplify" | "solve" | "diff" | "integrate"
    variable:   str   — optional; variable to differentiate/integrate/solve for
                        (defaults to x, or the only free symbol present)
"""
from __future__ import annotations

from typing import Any

import sympy
from sympy import (
    Add,
    E,
    Mul,
    Pow,
    Symbol,
    cancel,
    cos,
    diff,
    exp,
    expand,
    factor,
    integrate,
    log,
    pi,
    simplify,
    sin,
    tan,
)
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

_LOCALS: dict[str, Any] = {
    **{name: Symbol(name) for name in "xyzabcnmt"},
    "sin": sin,
    "cos": cos,
    "tan": tan,
    "exp": exp,
    "log": log,
    "pi": pi,
    "e": E,
}


def run(args: dict, session: Any) -> dict:
    expression: str = (args.get("expression") or "").strip()
    operation: str = (args.get("operation") or "simplify").strip().lower()
    variable: str | None = (args.get("variable") or "").strip() or None

    if not expression:
        return _error("No expression provided", "")

    try:
        steps, final = _compute(expression, operation, variable)
    except Exception as exc:  # noqa: BLE001
        return _error(str(exc), expression)

    return {
        "result": final,
        "ui_component": "AlgebraSteps",
        "display_data": {"steps": steps, "final": final},
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _error(msg: str, expression: str) -> dict:
    return {
        "result": f"Error: {msg}",
        "ui_component": "AlgebraSteps",
        "display_data": {
            "steps": [{"expr": expression or "(none)", "rule": "input"}],
            "final": f"Error: {msg}",
        },
    }


_TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)


def _parse(expression: str) -> sympy.Expr:
    # implicit_multiplication_application handles "2x" → 2*x, "3(x+1)" → 3*(x+1), etc.
    return parse_expr(expression, local_dict=_LOCALS, transformations=_TRANSFORMS)


def _fmt(expr: sympy.Expr) -> str:
    return sympy.latex(expr)


def _pick_var(expr: sympy.Expr, hint: str | None) -> Symbol:
    """Choose the variable to work with from a parsed expression."""
    free = sorted(expr.free_symbols, key=lambda s: s.name)
    if not free:
        return Symbol("x")
    if hint:
        matched = next((s for s in free if s.name == hint), None)
        if matched:
            return matched
    return next((s for s in free if s.name == "x"), free[0])


def _compute(
    expression: str, operation: str, variable: str | None
) -> tuple[list[dict], str]:
    dispatch = {
        "simplify": _op_simplify,
        "solve": _op_solve,
        "diff": _op_diff,
        "integrate": _op_integrate,
    }
    if operation not in dispatch:
        raise ValueError(
            f"Unknown operation {operation!r}. "
            "Expected one of: simplify, solve, diff, integrate"
        )
    return dispatch[operation](expression, variable)


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

def _op_simplify(expression: str, _variable: str | None) -> tuple[list[dict], str]:
    expr = _parse(expression)

    # For constant expressions (no free symbols) sympy evaluates immediately on
    # parse, so _fmt(expr) is already the answer.  Show the raw input as the
    # starting step so the student sees what was computed, not just "0 → 0".
    is_constant = not expr.free_symbols
    first_label = expression if is_constant else _fmt(expr)
    steps: list[dict] = [{"expr": first_label, "rule": "original expression"}]

    # Collect like terms: sympy may already have done this on parse.
    # Skip for constant expressions — the evaluate step below covers it.
    parsed_str = _fmt(expr)
    if not is_constant and parsed_str != expression:
        steps.append({"expr": parsed_str, "rule": "collect like terms"})

    if is_constant:
        steps.append({"expr": parsed_str, "rule": "evaluate"})
        return steps, parsed_str

    working = expr

    expanded = expand(working)
    if expanded != working:
        steps.append({"expr": _fmt(expanded), "rule": "expand brackets"})
        working = expanded

    cancelled = cancel(working)
    if cancelled != working:
        steps.append({"expr": _fmt(cancelled), "rule": "cancel common factors"})
        working = cancelled

    factored = factor(working)
    if factored != working:
        steps.append({"expr": _fmt(factored), "rule": "factorise"})
        working = factored

    result = simplify(working)
    if result != working:
        steps.append({"expr": _fmt(result), "rule": "simplify"})

    return steps, _fmt(result)


def _op_solve(expression: str, variable: str | None) -> tuple[list[dict], str]:
    eq_count = expression.count("=")
    if eq_count > 1:
        raise ValueError(
            "Expression contains more than one '=' sign. "
            "Please simplify to a single equation (e.g. 'lhs = rhs')."
        )

    if eq_count == 1:
        lhs_str, rhs_str = expression.split("=", 1)
        lhs = _parse(lhs_str.strip())
        rhs = _parse(rhs_str.strip())
        eq_expr = lhs - rhs
        steps: list[dict] = [{"expr": f"{_fmt(lhs)} = {_fmt(rhs)}", "rule": "original equation"}]
        steps.append({"expr": f"{_fmt(eq_expr)} = 0", "rule": "rearrange: move all terms to one side"})
    else:
        eq_expr = _parse(expression)
        steps: list[dict] = [{"expr": _fmt(eq_expr), "rule": "expression set equal to zero"}]

    var = _pick_var(eq_expr, variable)
    if not eq_expr.free_symbols:
        raise ValueError("No variables found — cannot solve a constant expression")

    # Show factored form when it reveals the roots directly.
    # Use sympy.factor() directly rather than isinstance(Mul) so single-factor
    # results (e.g. (x-3)**2) are also shown.
    factored = factor(eq_expr)
    if factored != eq_expr:
        steps.append({"expr": f"{_fmt(factored)} = 0", "rule": "factorise"})

    solutions = sympy.solve(eq_expr, var)

    if solutions is None or len(solutions) == 0:
        steps.append({"expr": "no real solution", "rule": f"solve for {var}"})
        return steps, "No real solution"

    sol_strs = [f"{var} = {_fmt(s)}" for s in solutions]
    for s in sol_strs:
        steps.append({"expr": s, "rule": f"solution for {var}"})

    return steps, ",   ".join(sol_strs)


def _op_diff(expression: str, variable: str | None) -> tuple[list[dict], str]:
    expr = _parse(expression)
    var = _pick_var(expr, variable)

    if not expr.free_symbols:
        return (
            [
                {"expr": _fmt(expr), "rule": "original expression"},
                {"expr": "0", "rule": "derivative of a constant = 0"},
            ],
            "0",
        )

    steps: list[dict] = [
        {"expr": _fmt(expr), "rule": f"differentiate with respect to {var}"}
    ]

    result = diff(expr, var)
    rule = _diff_rule(expr, var)
    steps.append({"expr": _fmt(result), "rule": rule})

    simplified = simplify(result)
    if simplified != result:
        steps.append({"expr": _fmt(simplified), "rule": "simplify"})

    return steps, _fmt(simplified)


def _op_integrate(expression: str, variable: str | None) -> tuple[list[dict], str]:
    expr = _parse(expression)
    free = expr.free_symbols

    if not free:
        var = Symbol(variable or "x")
        result_expr = expr * var
        final = f"{_fmt(result_expr)} + C"
        return (
            [
                {"expr": expression, "rule": "original expression"},
                {"expr": final, "rule": "integral of constant k is kx + C"},
            ],
            final,
        )

    var = _pick_var(expr, variable)
    steps: list[dict] = [
        {"expr": _fmt(expr), "rule": f"integrate with respect to {var}"}
    ]

    result = integrate(expr, var)
    rule = _integrate_rule(expr, var)
    steps.append({"expr": _fmt(result), "rule": rule})

    simplified = simplify(result)
    if simplified != result:
        steps.append({"expr": _fmt(simplified), "rule": "simplify"})

    final = f"{_fmt(simplified)} + C"
    steps.append({"expr": final, "rule": "add constant of integration"})

    return steps, final


# ---------------------------------------------------------------------------
# Rule label helpers
# ---------------------------------------------------------------------------

def _diff_rule(expr: sympy.Expr, var: Symbol) -> str:
    if isinstance(expr, Pow):
        base, exp_part = expr.args
        if base == var:
            return f"power rule: d/d{var}(u^n) = n·u^(n-1)"
    if isinstance(expr, Add):
        return "sum rule: differentiate each term separately"
    if isinstance(expr, Mul):
        non_var = [f for f in expr.args if not f.has(var)]
        if non_var:
            return "constant multiple rule: d/dx(c·f) = c·f′"
        return "product rule"
    if expr.has(sin) or expr.has(cos) or expr.has(tan):
        return "trigonometric derivative rule"
    if expr.has(exp):
        return "exponential derivative rule: d/dx(e^x) = e^x"
    if expr.has(log):
        return "logarithm derivative rule: d/dx(ln x) = 1/x"
    return "apply differentiation rules"


def _integrate_rule(expr: sympy.Expr, var: Symbol) -> str:
    if isinstance(expr, Pow):
        base, exp_part = expr.args
        if base == var:
            return "power rule: ∫x^n dx = x^(n+1)/(n+1)"
    if isinstance(expr, Add):
        return "sum rule: integrate each term separately"
    if isinstance(expr, Mul):
        non_var = [f for f in expr.args if not f.has(var)]
        if non_var:
            return "constant multiple rule: ∫c·f dx = c·∫f dx"
        return "apply integration rules"
    if expr.has(sin) or expr.has(cos) or expr.has(tan):
        return "trigonometric integral rule"
    if expr.has(exp):
        return "exponential integral rule: ∫e^x dx = e^x"
    if expr.has(log):
        return "integrate by parts"
    return "apply integration rules"
