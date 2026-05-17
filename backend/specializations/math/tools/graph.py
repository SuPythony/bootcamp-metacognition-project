"""Graph tool — matplotlib render to base64 PNG.

Returns: { result, ui_component: "GraphView", display_data: { image_url, caption } }

args:
    expression: str              — expression in x (e.g. "x**2 - 3*x + 2")
    x_range:    [number, number] — plot domain, e.g. [-5, 5]   (default: [-10, 10])
    variables:  dict             — substitute named values before plotting,
                                   e.g. {"a": 2, "b": -1} for "a*x**2 + b*x"
    caption:    str              — optional label; auto-generated if omitted
"""
from __future__ import annotations

import base64
import io
from typing import Any

# Use non-interactive Agg backend — safe on a headless server, no display needed.
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402 (must come after backend selection)
import numpy as np
import sympy
from sympy import Symbol, lambdify
from sympy.parsing.sympy_parser import (
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

_LOCALS: dict[str, Any] = {
    name: Symbol(name) for name in "xyzabcnmt"
}
_LOCALS.update({
    "sin": sympy.sin, "cos": sympy.cos, "tan": sympy.tan,
    "exp": sympy.exp, "log": sympy.log, "sqrt": sympy.sqrt,
    "pi": sympy.pi, "e": sympy.E,
    "abs": sympy.Abs,
})

_TRANSFORMS = standard_transformations + (implicit_multiplication_application,)

# Maximum y-distance rendered; clips asymptotes so the axes stay readable.
_Y_CLIP = 1e6


def run(args: dict, session: Any) -> dict:
    raw_expr = args.get("expression") or ""
    # LLM may pass a list of expressions to overlay on one plot (e.g. ["2x+3", "7"]).
    if isinstance(raw_expr, list):
        expressions = [str(e).strip() for e in raw_expr if str(e).strip()]
    elif isinstance(raw_expr, dict):
        return _error(
            "'expression' must be a string or list of strings, not a dict. "
            "Pass the formula directly, e.g. expression='x**2 + 1'."
        )
    else:
        expressions = [str(raw_expr).strip()]

    if not expressions or not any(expressions):
        return _error("No expression provided")

    x_range = args.get("x_range") or [-10, 10]
    variables: dict = args.get("variables") or {}
    caption: str = str(args.get("caption") or "").strip()

    if len(x_range) != 2:
        return _error("x_range must be [min, max]")
    try:
        xlo, xhi = float(x_range[0]), float(x_range[1])
    except (TypeError, ValueError):
        return _error("x_range values must be numbers")
    import math as _math
    if not (_math.isfinite(xlo) and _math.isfinite(xhi)):
        return _error("x_range values must be finite numbers")
    if xlo >= xhi:
        return _error("x_range must satisfy min < max")

    try:
        image_url, auto_caption = _render(expressions, x_range, variables)
    except Exception as exc:  # noqa: BLE001
        return _error(str(exc))

    result_label = ", ".join(expressions)
    return {
        "result": f"Graph of {result_label}",
        "ui_component": "GraphView",
        "display_data": {
            "image_url": image_url,
            "caption": caption or auto_caption,
        },
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _error(msg: str) -> dict:
    return {
        "result": f"Error: {msg}",
        "ui_component": "GraphView",
        "display_data": {"image_url": "", "caption": f"Error: {msg}"},
    }


def _eval_expr(expression: str, x_vals: np.ndarray, variables: dict) -> np.ndarray:
    """Parse and evaluate one expression over x_vals; returns y array (NaN where undefined)."""
    sym_expr = parse_expr(expression, local_dict=_LOCALS, transformations=_TRANSFORMS)
    subs = {Symbol(k): float(v) for k, v in variables.items() if k != "x"}
    if subs:
        sym_expr = sym_expr.subs(subs)
    # After substitution, only x may remain as a free symbol. Validate up front
    # so the failure message is actionable rather than a raw lambdify NameError
    # surfaced from inside the numpy errstate block.
    remaining = {s for s in sym_expr.free_symbols if s.name != "x"}
    if remaining:
        names = ", ".join(sorted(s.name for s in remaining))
        raise ValueError(
            f"Expression '{expression}' has unresolved symbols: {names}. "
            f"Provide values via the variables argument, e.g. variables={{'{next(iter(sorted(s.name for s in remaining)))}': 1.0}}."
        )
    f = lambdify(Symbol("x"), sym_expr, modules=["numpy"])
    with np.errstate(divide="ignore", invalid="ignore"):
        raw = f(x_vals)
    # Constants (e.g. y=7) return a scalar — broadcast to match x_vals shape.
    y_vals = np.broadcast_to(np.asarray(raw, dtype=complex), x_vals.shape).copy()
    real_mask = np.isreal(y_vals)
    complex_fraction = (~real_mask).sum() / max(len(y_vals), 1)
    if complex_fraction > 0.1:
        import logging as _logging
        _logging.getLogger("app.tools.graph").warning(
            "Expression '%s' produces complex values for %.0f%% of the range; "
            "plotting real part only.",
            expression,
            complex_fraction * 100,
        )
    y_plot = np.where(real_mask, y_vals.real, np.nan)
    return np.where(np.abs(y_plot) > _Y_CLIP, np.nan, y_plot)


def _render(
    expressions: list[str],
    x_range: list,
    variables: dict,
) -> tuple[str, str]:
    """Plot one or more expressions over x_range, return (data-URL, auto_caption)."""
    span = abs(float(x_range[1]) - float(x_range[0]))
    n_points = max(500, min(2000, int(span * 50)))
    x_vals = np.linspace(float(x_range[0]), float(x_range[1]), n_points)
    curves = [(expr, _eval_expr(expr, x_vals, variables)) for expr in expressions]
    auto_caption = _caption(expressions, variables)
    image_url = _fig_to_dataurl(x_vals, curves, auto_caption, x_range)
    return image_url, auto_caption


_LINE_COLORS = ["#4f6df5", "#e05c2a", "#27a862", "#9b30d9", "#d4a017"]


def _fig_to_dataurl(
    x_vals: np.ndarray,
    curves: list[tuple[str, np.ndarray]],
    caption: str,
    x_range: list,
) -> str:
    fig, ax = plt.subplots(figsize=(6, 4), dpi=100)

    multi = len(curves) > 1
    for i, (label, y_vals) in enumerate(curves):
        color = _LINE_COLORS[i % len(_LINE_COLORS)]
        ax.plot(x_vals, y_vals, linewidth=2, color=color,
                label=f"y = {label}" if multi else None)

    ax.axhline(0, color="black", linewidth=0.8, linestyle="--", alpha=0.4)
    ax.axvline(0, color="black", linewidth=0.8, linestyle="--", alpha=0.4)
    ax.set_xlim(x_range[0], x_range[1])
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title(caption, fontsize=11)
    ax.grid(True, alpha=0.3)
    if multi:
        ax.legend(fontsize=9)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)

    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _caption(expressions: list[str], variables: dict) -> str:
    label = "  &  ".join(f"y = {e}" for e in expressions)
    if variables:
        subs_str = ", ".join(f"{k}={v}" for k, v in variables.items())
        return f"{label}  ({subs_str})"
    return label
