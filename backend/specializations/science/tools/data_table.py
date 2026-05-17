"""Data table tool. Passes tabular observation data through to the DataTable UI component.

Input: { "columns": ["Time (s)", "Distance (m)"], "rows": [[0, 0], [1, 4.9], ...],
         "title": "optional caption" }
Output: the same structure wrapped for the frontend renderer.
"""

from __future__ import annotations


def run(args: dict, session) -> dict:
    columns = args.get("columns", [])
    rows = args.get("rows", [])
    title = args.get("title", "")

    if not isinstance(columns, list):
        return {
            "result": "Error: 'columns' must be a list of strings",
            "display_data": {},
            "ui_component": "DataTable",
        }
    if not isinstance(rows, list):
        return {
            "result": "Error: 'rows' must be a list of lists",
            "display_data": {},
            "ui_component": "DataTable",
        }

    n_cols = len(columns)
    cleaned_rows = []
    for row in rows:
        if isinstance(row, list):
            # Pad or truncate to match column count
            cleaned_rows.append((row + [None] * n_cols)[:n_cols])

    summary = f"{len(cleaned_rows)} row(s) × {n_cols} column(s)"
    if title:
        summary = f"{title}: {summary}"

    return {
        "result": summary,
        "display_data": {
            "columns": columns,
            "rows": cleaned_rows,
            "title": title,
        },
        "ui_component": "DataTable",
    }
