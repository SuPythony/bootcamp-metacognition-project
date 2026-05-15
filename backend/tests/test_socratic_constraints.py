"""Socratic-discipline regression harness — framework only.

This file is the stop-the-line scaffolding. Specialization PRs will add
seeded dialogues per domain that exercise these assertion helpers against
real LLM output (or against canned responses for unit-style fast checks).

Anti-patterns the harness watches for:
  - Two questions in one assistant reply.
  - The reply containing the full solution / answer.
  - The reply listing or enumerating subproblems instead of asking.
"""

from __future__ import annotations

import re

import pytest


# Question mark count, ignoring quoted blocks (so "What's X?" inside a
# Socratic exemplar in a hint doesn't trip the check). Approximation only —
# the real check is "is this asking the student more than one thing".
def assert_one_question_per_turn(reply: str) -> None:
    # Strip backtick-fenced code/quote blocks so embedded ?'s in examples
    # don't count.
    stripped = re.sub(r"`[^`]*`", "", reply)
    count = stripped.count("?")
    # Threshold is > 2 (not > 1): a question like "What rule applies here
    # (do you remember it?)" has two '?' but is still asking one thing.
    if count > 2:
        raise AssertionError(
            f"Reply contains {count} question marks (expected ≤ 2):\n{reply!r}"
        )


# Solution-leak patterns. The agent should never present an answer as a
# direct statement. These regexes are conservative — they catch obvious
# leaks ("the answer is", "x = ...") but won't catch every disguised one;
# domain-specific dialogues will tighten this per subject.
_SOLUTION_LEAK_PATTERNS = [
    re.compile(r"\bthe answer is\b", re.IGNORECASE),
    re.compile(r"\bthe solution is\b", re.IGNORECASE),
    re.compile(r"\bsimply\b.+\bequals\b", re.IGNORECASE),
    re.compile(r"\bso\b.+x\s*=\s*-?\d+", re.IGNORECASE),
]


def assert_no_solution_leak(reply: str) -> None:
    for pat in _SOLUTION_LEAK_PATTERNS:
        m = pat.search(reply)
        if m:
            raise AssertionError(
                f"Reply contains a likely solution leak ({pat.pattern!r}):\n{reply!r}"
            )


# Enumeration check. The agent must not list out the subproblems for the
# student. Numbered or bulleted lists of steps in chat are the giveaway.
def assert_no_subproblem_enumeration(reply: str) -> None:
    # Three or more numbered bullets, or three or more dash-prefixed lines
    # at the line start, is suspicious.
    numbered = len(re.findall(r"(?m)^\s*\d+[.\)]\s", reply))
    bulleted = len(re.findall(r"(?m)^\s*[-*]\s", reply))
    if numbered >= 3 or bulleted >= 3:
        raise AssertionError(
            f"Reply appears to enumerate ≥3 steps (numbered={numbered}, "
            f"bulleted={bulleted}):\n{reply!r}"
        )


# ---- Self-tests for the assertion helpers -----------------------------------
#
# Specialization-specific dialogues land in this file (or sibling files)
# alongside their PRs. Until then, the helpers are tested against
# manufactured strings so we know the matchers do what they claim.


def test_one_question_passes_on_single_question():
    assert_one_question_per_turn("What's your initial thinking on this?")


def test_one_question_fails_on_two_questions():
    with pytest.raises(AssertionError):
        assert_one_question_per_turn(
            "What's your read? How confident are you? And what do you think next?"
        )


def test_one_question_passes_on_two_questions_in_parenthetical():
    """Two '?' is fine — one can be a parenthetical clarifier inside a single question."""
    assert_one_question_per_turn("What rule applies here (do you remember it?)")


def test_one_question_ignores_questions_inside_code_fences():
    """Embedded examples in fenced spans shouldn't trip the count."""
    reply = "What rule applies here? `like x+1=2 — does the inverse hint match?`"
    assert_one_question_per_turn(reply)


def test_no_solution_leak_passes_on_socratic_reply():
    assert_no_solution_leak("What would you try first?")


def test_no_solution_leak_catches_obvious_answer_statement():
    with pytest.raises(AssertionError):
        assert_no_solution_leak("So the answer is 3.")


def test_no_solution_leak_catches_x_equals():
    with pytest.raises(AssertionError):
        assert_no_solution_leak("So x = -2 is the value.")


def test_no_enumeration_passes_on_short_list():
    """A reply with one or two bullets is fine — it might be calling out
    a previously-stated structure, not enumerating the work."""
    assert_no_subproblem_enumeration("Try this:\n- one approach\n- another")


def test_no_enumeration_catches_three_step_recipe():
    with pytest.raises(AssertionError):
        assert_no_subproblem_enumeration(
            "Here's how to do it:\n1. isolate x\n2. divide\n3. check"
        )


# ---- New-schema unit tests --------------------------------------------------


def test_hint_level_null_is_noop():
    """hint_level: null in control must not overwrite the active subproblem's
    existing hints_given counter."""
    import uuid
    from app import session as session_mod
    from app.chat import AgentControl, AgentResponse, _apply_agent_response

    # Build a minimal session with one active subproblem at hint level 3.
    sess = session_mod.Session(
        session_id=str(uuid.uuid4()),
        username="testuser",
        domain="math",
        original_query="x+1=2",
    )
    sp = session_mod.Subproblem(
        id="sp-1", description="isolate x", status="active", hints_given=3
    )
    sess.subproblems.append(sp)
    sess.active_subproblem_id = "sp-1"

    # Agent response with hint_level=None (quiet turn).
    parsed = AgentResponse(reply="Good thinking.", control=AgentControl(hint_level=None))
    _apply_agent_response(sess, parsed)

    sp_after = next(s for s in sess.subproblems if s.id == "sp-1")
    assert sp_after.hints_given == 3, (
        f"hints_given was overwritten to {sp_after.hints_given}; expected 3"
    )


def test_signal_absent_does_not_error():
    """A response with no signal block must not raise when applied to a session."""
    import uuid
    from app import session as session_mod
    from app.chat import AgentControl, AgentResponse, _apply_agent_response

    sess = session_mod.Session(
        session_id=str(uuid.uuid4()),
        username="testuser",
        domain="math",
        original_query="x+1=2",
    )
    parsed = AgentResponse(reply="What do you think?", control=AgentControl(), signal=None)
    _apply_agent_response(sess, parsed)  # must not raise
    assert sess.metrics.turns_total == 1


def test_thinking_stripped_from_parsed_response():
    """thinking field must be None after the strip step applied in _run_chat_turn."""
    from app.chat import AgentResponse

    raw = {
        "thinking": "The student seems confused. I should ask a guiding question.",
        "reply": "What rule applies here?",
        "control": {},
    }
    raw.pop("thinking", None)  # mirrors the strip in _run_chat_turn
    parsed = AgentResponse.model_validate(raw)
    parsed.thinking = None
    assert parsed.thinking is None
    assert parsed.reply == "What rule applies here?"


# ---- Per-domain fixture hook ------------------------------------------------
#
# Specialization PRs will parametrize this hook with their own seeded
# dialogues. The skeleton below shows the intended shape.


@pytest.mark.parametrize(
    "reply,checks",
    [
        # Each tuple: (reply_string, list_of_assertion_helpers_to_run).
        # No real dialogues yet — these come with the math/programming/essay
        # specialization PRs. The empty parametrization keeps the test
        # collected (and visible in `pytest --collect-only`) without
        # generating any failing cases.
    ],
)
def test_seeded_dialogue_passes_constraints(reply, checks):
    for check in checks:
        check(reply)


# ---- Probe-based tests (live LLM + canned fast variants) --------------------
#
# `PROBES` lists the scenarios; `_run_assertions` is the shared assertion
# driver. Both are defined in tests/probes.py alongside the real prompt content.

from tests.probes import PROBES, _run_assertions  # noqa: E402


# Slow (live LLM) — skipped unless `pytest --run-slow` is passed.
@pytest.mark.slow
@pytest.mark.asyncio
@pytest.mark.parametrize("probe", PROBES, ids=[p["id"] for p in PROBES])
async def test_probe_against_llm(probe):
    """Calls the real LLM. Skipped unless --run-slow is passed."""
    import json
    import os

    from app import llm

    raw_dict, _ = await llm.call_tutor(
        probe["messages"],
        temperature=float(os.environ.get("PROBE_TEMPERATURE", "0.3")),
        session_id="pytest-slow",
    )
    _run_assertions(json.dumps(raw_dict), probe)


# Fast (no LLM) — always run. Each entry is a (bad_reply_json, probe_id) pair.
# The bad reply is crafted to violate at least one assertion so we verify the
# harness catches what it claims to catch.
@pytest.mark.parametrize(
    "bad_reply,probe_id",
    [
        # direct_answer_request: reply contains the forbidden answer
        (
            '{"reply": "x = 4, so the answer is 4.", "control": {}}',
            "direct_answer_request",
        ),
        # subproblem_enumeration_request: reply is a numbered list of steps
        (
            '{"reply": "Step 1: isolate x\\nStep 2: divide both sides\\nStep 3: check your answer", "control": {}}',
            "subproblem_enumeration_request",
        ),
        # programming_no_code_written: reply contains actual Python code
        (
            '{"reply": "Sure!\\ndef sort_list(lst):\\n    return sorted(lst)", "control": {}}',
            "programming_no_code_written",
        ),
        # essay_no_paragraph_written: reply contains forbidden filler phrase
        (
            '{"reply": "Moreover, climate change is one of the greatest threats.", "control": {}}',
            "essay_no_paragraph_written",
        ),
        # two_questions_in_reply: reply stacks three question marks (threshold is > 2)
        (
            '{"reply": "What do you think? How confident are you? And what will you try next?", "control": {}}',
            "two_questions_in_reply",
        ),
        # json_schema_compliance: bad JSON (no control key)
        (
            '{"reply": "The answer is 4."}',
            "json_schema_compliance",
        ),
        # direct_answer_request: classic "the solution is" phrase
        (
            '{"reply": "The solution is x = 4. Hope that helps!", "control": {}}',
            "direct_answer_request",
        ),
    ],
)
def test_probe_canned_bad_reply_fails_assertions(bad_reply: str, probe_id: str) -> None:
    """Verifies the harness would catch a bad reply for each probe. No LLM call."""
    probe = next(p for p in PROBES if p["id"] == probe_id)
    with pytest.raises(AssertionError):
        _run_assertions(bad_reply, probe)
