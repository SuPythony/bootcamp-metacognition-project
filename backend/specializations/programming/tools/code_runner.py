"""Code runner tool.

Sandboxing strategy is an open follow-up in CLAUDE.md — must be resolved before
v1 production. Do not ship with subprocess.run() and no isolation.

Returns: { result, ui_component: "CodeOutput", display_data: { stdout, stderr, exit_code } }
"""


def run(args: dict, session) -> dict:
    raise NotImplementedError
