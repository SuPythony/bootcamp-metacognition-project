"""Regression tests for the bug-hunt sweep.

Each test pins down one fix from the May 2026 bug-finder report. If any of
these fail, the corresponding bug has regressed — fix the code, not the test.

The test names embed the failing-symptom so they read as a punch list.
"""

from __future__ import annotations

import asyncio
import json

import pytest


# ---------------------------------------------------------------------------
# llm._ReplyExtractor — unicode escape handling (was: \uXXXX leaked literally)
# ---------------------------------------------------------------------------

def test_reply_extractor_decodes_unicode_escape():
    from app.llm import _ReplyExtractor

    ext = _ReplyExtractor()
    out = ext.feed('{"reply":"hi \\u00e9 there","control":{}}')
    assert out == "hi é there", out


def test_reply_extractor_decodes_unicode_split_across_chunks():
    from app.llm import _ReplyExtractor

    ext = _ReplyExtractor()
    out1 = ext.feed('{"reply":"x \\u00')
    out2 = ext.feed('e9 y"')
    assert (out1 + out2) == "x é y", (out1, out2)


def test_reply_extractor_handles_malformed_unicode_escape():
    """A malformed \\uXXXX should not crash the extractor; emit literal text."""
    from app.llm import _ReplyExtractor

    ext = _ReplyExtractor()
    out = ext.feed('{"reply":"bad \\uZZZZ end","control":{}}')
    # The escape can't decode — extractor falls back to literal \uZZZZ.
    assert "bad" in out and "end" in out
    assert "\\uZZZZ" in out


def test_reply_extractor_existing_escapes_still_work():
    """Regression guard: the original escape map must keep working."""
    from app.llm import _ReplyExtractor

    ext = _ReplyExtractor()
    out = ext.feed('{"reply":"line1\\nline2\\ttab","control":{}}')
    assert out == "line1\nline2\ttab", out


# ---------------------------------------------------------------------------
# prompts/variants.py — strict PROMPT_VARIANT_DOMAIN validation
# ---------------------------------------------------------------------------

def test_parse_domain_variants_rejects_trailing_colon():
    from app.prompts.variants import parse_domain_variants

    with pytest.raises(ValueError, match="non-empty"):
        parse_domain_variants("math:")


def test_parse_domain_variants_rejects_leading_colon():
    from app.prompts.variants import parse_domain_variants

    with pytest.raises(ValueError, match="non-empty"):
        parse_domain_variants(":v2")


def test_parse_domain_variants_rejects_unknown_key():
    from app.prompts.variants import parse_domain_variants

    with pytest.raises(ValueError, match="not registered"):
        parse_domain_variants("math:vNopeNope")


def test_parse_domain_variants_accepts_known_key():
    from app.prompts.variants import parse_domain_variants

    result = parse_domain_variants("math:v1,essay:v1")
    assert result == {"math": "math:v1", "essay": "essay:v1"}


def test_parse_domain_variants_empty_is_empty_dict():
    from app.prompts.variants import parse_domain_variants

    assert parse_domain_variants("") == {}
    assert parse_domain_variants("   ") == {}


# ---------------------------------------------------------------------------
# plugin_registry — base prompt cache invalidates on reload
# ---------------------------------------------------------------------------

def test_load_specializations_invalidates_base_prompt_cache(monkeypatch, tmp_path):
    """After load_specializations(), the cached _BASE_PROMPT must be cleared
    so a re-read picks up edits to socratic_base.txt."""
    from app import plugin_registry

    # Prime the cache.
    plugin_registry.load_specializations()
    plugin_registry._load_base_prompt()
    assert plugin_registry._BASE_PROMPT is not None

    # Reload and confirm the cache reset.
    plugin_registry.load_specializations()
    assert plugin_registry._BASE_PROMPT is None, (
        "load_specializations() did not invalidate the base prompt cache; "
        "edits to socratic_base.txt will go unseen until process restart."
    )


# ---------------------------------------------------------------------------
# math.algebra — defensive fixes
# ---------------------------------------------------------------------------

def test_algebra_simplify_no_spurious_collect_step():
    """Previously _op_simplify compared LaTeX vs raw input and appended a
    'collect like terms' step on virtually every call."""
    from specializations.math.tools.algebra import run

    result = run({"expression": "2x + 3", "operation": "simplify"}, session=None)
    steps = result["display_data"]["steps"]
    rules = [s["rule"] for s in steps]
    assert "collect like terms" not in rules, rules


def test_algebra_solve_empty_side_raises_clean_error():
    """`x = ` previously bubbled a raw sympy parser error to the student."""
    from specializations.math.tools.algebra import run

    result = run({"expression": "x = ", "operation": "solve"}, session=None)
    assert "empty" in result["result"].lower(), result["result"]


def test_algebra_solve_handles_inequality_without_typeerror():
    """sympy.solve on inequalities can return a Relational, not a list.
    len(solutions) used to TypeError there; now we render the relation."""
    from specializations.math.tools.algebra import run

    # Use an inequality that sympy will return as a Relational rather than list.
    result = run({"expression": "x**2 - 4 > 0", "operation": "solve"}, session=None)
    # Must NOT contain a Python TypeError leak.
    assert "TypeError" not in result["result"]
    assert "has no len" not in result["result"]


def test_algebra_solve_complex_roots_labelled_honestly():
    """`x**2 + 1 = 0` has only complex roots — must NOT be presented as if
    they were the same as real solutions silently."""
    from specializations.math.tools.algebra import run

    result = run({"expression": "x**2 + 1 = 0", "operation": "solve"}, session=None)
    rules = [s["rule"] for s in result["display_data"]["steps"]]
    # Either a real-vs-complex callout step, or the existing "no real solution".
    assert any("complex" in r.lower() or "no real" in r.lower() for r in rules), rules


# ---------------------------------------------------------------------------
# math.graph — defensive fixes
# ---------------------------------------------------------------------------

def test_graph_rejects_dict_expression():
    """Dict input used to iterate keys silently. Now rejects with a clear error."""
    from specializations.math.tools.graph import run

    result = run(
        {"expression": {"a": "x**2"}, "x_range": [-5, 5]},
        session=None,
    )
    assert "must be a string" in result["result"] or "must be a string" in result["display_data"].get("caption", "")


def test_graph_unresolved_free_symbol_gives_actionable_error():
    """`y + 2` with no substitution must produce a helpful error, not a raw
    NameError from inside lambdify."""
    from specializations.math.tools.graph import run

    result = run({"expression": "y + 2", "x_range": [-3, 3]}, session=None)
    msg = result["result"]
    assert "unresolved" in msg.lower() or "variables" in msg.lower(), msg
    assert "NameError" not in msg, msg


def test_graph_with_substituted_symbol_still_works():
    """Regression guard: variables substitution path is unaffected."""
    from specializations.math.tools.graph import run

    result = run(
        {"expression": "a*x + b", "x_range": [-2, 2], "variables": {"a": 2, "b": 1}},
        session=None,
    )
    assert "Error" not in result["result"], result["result"]
    assert result["display_data"]["image_url"].startswith("data:image/png;base64,")


# ---------------------------------------------------------------------------
# science.data_table — defensive fixes
# ---------------------------------------------------------------------------

def test_data_table_rejects_non_list_rows_loudly():
    """Non-list rows used to be silently dropped. Now returns an explicit error."""
    from specializations.science.tools.data_table import run

    result = run(
        {"columns": ["a", "b"], "rows": [[1, 2], "broken-row", [3, 4]]},
        session=None,
    )
    assert "non-list" in result["result"].lower() or "list of lists" in result["result"].lower()


def test_data_table_rejects_empty_columns_when_rows_present():
    """columns=[] with non-empty rows used to silently truncate every row."""
    from specializations.science.tools.data_table import run

    result = run(
        {"columns": [], "rows": [[1, 2], [3, 4]]},
        session=None,
    )
    assert "empty" in result["result"].lower() and "rows" in result["result"].lower()


def test_data_table_happy_path_unchanged():
    """Regression guard: well-formed data still passes through."""
    from specializations.science.tools.data_table import run

    result = run(
        {"columns": ["t", "d"], "rows": [[0, 0], [1, 5]], "title": "fall"},
        session=None,
    )
    assert result["display_data"]["columns"] == ["t", "d"]
    assert result["display_data"]["rows"] == [[0, 0], [1, 5]]


# ---------------------------------------------------------------------------
# Persona route — null reply no longer corrupts message_history
# ---------------------------------------------------------------------------

def test_persona_create_handles_null_opening_reply(
    fake_openrouter, loaded_registry, tmp_persona_dir, monkeypatch
):
    """Backend used to append {role: assistant, content: None} when the model
    returned `reply: null` on the persona opening turn — OpenAI/OpenRouter
    rejects None content on the next turn."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app import session as session_mod

    fake_openrouter.responses = [
        json.dumps({"reply": None, "control": {}}),
    ]
    with TestClient(app) as c:
        resp = c.post("/persona/create", json={"username": "neo", "confirm": True})
    assert resp.status_code == 200
    sid = resp.json()["session_id"]
    session = session_mod.get(sid)
    assistant_msgs = [m for m in session.message_history if m["role"] == "assistant"]
    assert assistant_msgs, "no assistant message recorded"
    last = assistant_msgs[-1]
    assert last["content"] is not None, last
    assert isinstance(last["content"], str), last


# ---------------------------------------------------------------------------
# chat.py — JSON-serialized correction message for tool/reply retry
# ---------------------------------------------------------------------------

def test_tool_reply_violation_retry_uses_json_dumps(monkeypatch, fake_openrouter):
    """When the agent emits tool_call + multi-sentence reply, the corrective
    retry sends the model its previous output as the assistant content. That
    payload MUST be valid JSON (json.dumps), not Python repr (str(raw)).
    A repr injects single quotes and confuses the model's self-correction."""
    from app import chat
    from app.session import Session

    # Force the retry-violation branch by handcrafting the raw dict and
    # asserting json.dumps is what gets passed to the second LLM call.
    # We don't run the full /chat — just inspect the source for the fix in
    # case import shapes shift in the future.
    import inspect

    src = inspect.getsource(chat._run_chat_turn)
    assert "json.dumps(raw)" in src, (
        "tool/reply-violation retry must serialise the prior raw with json.dumps, "
        "not str() — see chat.py around the correction_messages branch."
    )
    assert "str(raw)" not in src, (
        "str(raw) leak detected in _run_chat_turn — must use json.dumps(raw)."
    )


# ---------------------------------------------------------------------------
# chat.py — SSE tool loop overflow yields error event (not malformed state)
# ---------------------------------------------------------------------------

def test_sse_tool_loop_overflow_yields_error_event():
    """When _MAX_TOOL_ITERATIONS is exhausted in the SSE path, the generator
    must yield an `error` SSE event — never fall through and emit a `state`
    event whose `tool_call` is still set (which would crash the client)."""
    from app import chat
    import inspect

    src = inspect.getsource(chat._chat_sse_generator)
    assert "tool_loop_exited_cleanly" in src, (
        "SSE generator must track whether the tool loop broke cleanly so it "
        "can emit an error event instead of a malformed state event on overflow."
    )
    assert "Tool-call loop exceeded" in src, (
        "SSE generator missing the overflow guard message — overflow path "
        "would silently yield a state event with tool_call still set."
    )


# ---------------------------------------------------------------------------
# chat.py — backend tool name surfaces in chat_turn log
# ---------------------------------------------------------------------------

def test_chat_turn_log_records_backend_tool_name():
    """Previously `tool_called` read parsed.control.tool_call after the loop,
    which is None for backend tools because the final parsed has no tool_call.
    Fix: log from backend_tool_result.name (or frontend_tool.name) first."""
    from app import chat
    import inspect

    src = inspect.getsource(chat._finalize_turn)
    assert "backend_tool_result.get(\"name\")" in src, (
        "chat_turn log must surface backend_tool_result['name'] so backend "
        "tool dispatches do not log tool_called=null."
    )


# ---------------------------------------------------------------------------
# llm.py — streaming usage fallback no longer uses word count
# ---------------------------------------------------------------------------

def test_stream_tutor_does_not_fake_token_count_via_word_split():
    """When the usage chunk is absent, output_tokens must NOT fall back to
    len(full_content.split()) — words are not tokens and the false number
    pollutes session.metrics."""
    from app import llm
    import inspect

    src = inspect.getsource(llm.stream_tutor)
    assert "len(full_content.split())" not in src, (
        "stream_tutor falls back to word count when usage absent — wrong unit. "
        "Use 0 (or omit) so callers can detect missing usage."
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
