"""Science graph tool.

Two calling modes:
  1. x/y arrays  — { "x": [...], "y": [...], "x_label": "...", "y_label": "...", "caption": "..." }
     Plots raw observation data as a line graph (typical for science experiments).
  2. expression  — { "expression": "9.8*t", "x_range": [0, 5], ... }
     Delegates to the math graph engine (sympy + matplotlib) for formula curves.

Returns: { result, ui_component: "GraphView", display_data: { image_url, caption } }
"""
from __future__ import annotations

import base64
import io
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from specializations.math.tools.graph import run as _math_graph_run


def run(args: dict, session: Any) -> dict:
    x = args.get("x")
    y = args.get("y")

    # x/y array mode
    if x is not None or y is not None:
        return _run_xy(args)

    # expression mode — delegate to math graph
    return _math_graph_run(args, session)


def _run_xy(args: dict) -> dict:
    x_vals = args.get("x") or []
    y_vals = args.get("y") or []
    x_label = str(args.get("x_label") or "x").strip()
    y_label = str(args.get("y_label") or "y").strip()
    caption = str(args.get("caption") or "").strip()

    if not isinstance(x_vals, list) or not isinstance(y_vals, list):
        return _error("'x' and 'y' must be lists of numbers")
    if len(x_vals) == 0:
        return _error("'x' array is empty")
    if len(x_vals) != len(y_vals):
        return _error(
            f"'x' and 'y' must have the same length (got {len(x_vals)} and {len(y_vals)})"
        )

    try:
        x_nums = [float(v) for v in x_vals]
        y_nums = [float(v) for v in y_vals]
    except (TypeError, ValueError) as exc:
        return _error(f"Non-numeric value in x/y data: {exc}")

    auto_caption = caption or f"{y_label} vs {x_label}"

    try:
        image_url = _plot_xy(x_nums, y_nums, x_label, y_label, auto_caption)
    except Exception as exc:  # noqa: BLE001
        return _error(str(exc))

    return {
        "result": f"Graph of {y_label} vs {x_label} ({len(x_nums)} points)",
        "ui_component": "GraphView",
        "display_data": {"image_url": image_url, "caption": auto_caption},
    }


def _plot_xy(x: list, y: list, x_label: str, y_label: str, caption: str) -> str:
    fig, ax = plt.subplots(figsize=(6, 4), dpi=100)
    ax.plot(x, y, "o-", linewidth=2, markersize=5, color="#4f6df5")
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_title(caption, fontsize=11)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return "data:image/png;base64," + base64.b64encode(buf.read()).decode("ascii")


def _error(msg: str) -> dict:
    return {
        "result": f"Error: {msg}",
        "ui_component": "GraphView",
        "display_data": {"image_url": "", "caption": f"Error: {msg}"},
    }
