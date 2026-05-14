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
from sympy import Symbol, lambdify, sympify

_LOCALS: dict[str, Any] = {
    name: Symbol(name) for name in "xyzabcnmt"
}
_LOCALS.update({
    "sin": sympy.sin, "cos": sympy.cos, "tan": sympy.tan,
    "exp": sympy.exp, "log": sympy.log, "sqrt": sympy.sqrt,
    "pi": sympy.pi, "e": sympy.E,
    "abs": sympy.Abs,
})

# Maximum y-distance rendered; clips asymptotes so the axes stay readable.
_Y_CLIP = 1e6


def run(args: dict, session: Any) -> dict:
    expression: str = (args.get("expression") or "").strip()
    x_range = args.get("x_range") or [-10, 10]
    variables: dict = args.get("variables") or {}
    caption: str = (args.get("caption") or "").strip()

    if not expression:
        return _error("No expression provided")

    if len(x_range) != 2 or x_range[0] >= x_range[1]:
        return _error("x_range must be [min, max] with min < max")

    try:
        image_url, auto_caption = _render(expression, x_range, variables)
    except Exception as exc:  # noqa: BLE001
        return _error(str(exc))

    return {
        "result": f"Graph of y = {expression}",
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


def _render(
    expression: str,
    x_range: list,
    variables: dict,
) -> tuple[str, str]:
    """Plot expression over x_range, return (data-URL, auto_caption)."""
    sym_expr = sympify(expression, locals=_LOCALS)

    # Substitute any provided variable values
    subs = {Symbol(k): float(v) for k, v in variables.items() if k != "x"}
    if subs:
        sym_expr = sym_expr.subs(subs)

    # Build a fast numpy-backed callable
    x_sym = Symbol("x")
    f = lambdify(x_sym, sym_expr, modules=["numpy"])

    x_vals = np.linspace(float(x_range[0]), float(x_range[1]), 500)

    with np.errstate(divide="ignore", invalid="ignore"):
        y_vals = np.asarray(f(x_vals), dtype=complex)

    # Drop imaginary parts (e.g. sqrt of negative x values)
    real_mask = np.isreal(y_vals)
    y_plot = np.where(real_mask, y_vals.real, np.nan)

    # Clip extreme values so asymptotes don't collapse the useful range
    y_plot = np.where(np.abs(y_plot) > _Y_CLIP, np.nan, y_plot)

    auto_caption = _caption(expression, variables)
    image_url = _fig_to_dataurl(x_vals, y_plot, auto_caption, x_range)
    return image_url, auto_caption


def _fig_to_dataurl(
    x_vals: np.ndarray,
    y_vals: np.ndarray,
    caption: str,
    x_range: list,
) -> str:
    fig, ax = plt.subplots(figsize=(6, 4), dpi=100)

    ax.plot(x_vals, y_vals, linewidth=2, color="#4f6df5")
    ax.axhline(0, color="black", linewidth=0.8, linestyle="--", alpha=0.4)
    ax.axvline(0, color="black", linewidth=0.8, linestyle="--", alpha=0.4)
    ax.set_xlim(x_range[0], x_range[1])
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title(caption, fontsize=11)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)

    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _caption(expression: str, variables: dict) -> str:
    if variables:
        subs_str = ", ".join(f"{k}={v}" for k, v in variables.items())
        return f"y = {expression}  ({subs_str})"
    return f"y = {expression}"
