"""Probe dialogues for the Socratic discipline regression harness.

Each probe is a dict that describes a scenario, a set of messages to send to
the LLM, and the assertions to run on the reply. Probes are used by both:
  - tests/run_probes.py  (manual CLI runner, calls real LLM directly)
  - tests/test_socratic_constraints.py  (pytest integration)

`_run_assertions(raw_output, probe)` is the shared assertion driver. It raises
AssertionError with a descriptive message on any violation.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Make sure the backend package is importable when this module is imported
# directly (e.g. from run_probes.py) without going through the pytest conftest.
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.prompts.variants import load_base_prompt, load_prompt  # noqa: E402


# ---------------------------------------------------------------------------
# Phase-aware prompt loader for probes
# ---------------------------------------------------------------------------

def _load_probe_prompt(
    domain: str,
    phase: str = "clarification",
    base_variant: str | None = None,
    domain_variant: str | None = None,
) -> str:
    """Load core.txt + phase_{phase}.txt + domain prompt for probe use.

    No real Session needed — passes a minimal stub with just the phase set.
    Calibration and reflection fields are empty so no context blocks are added.
    """
    class _PhaseStub:
        def __init__(self, p: str) -> None:
            self.phase = p
            self.calibration_points: list = []
            self.pending_reflection_index = None
            self.reflection_prompts: list = []

    base = load_base_prompt(variant_key=base_variant, session=_PhaseStub(phase))
    domain_text = load_prompt(domain, variant_key=domain_variant)
    return base + "\n\n" + domain_text


# ---------------------------------------------------------------------------
# Load real prompt content from disk via the variant registry
# ---------------------------------------------------------------------------

_MATH_CLARIFICATION_PROMPT    = _load_probe_prompt("math",        "clarification")
_MATH_SOLVING_PROMPT          = _load_probe_prompt("math",        "solving")
_PROG_CLARIFICATION_PROMPT    = _load_probe_prompt("programming", "clarification")
_ESSAY_CLARIFICATION_PROMPT   = _load_probe_prompt("essay",       "clarification")
_ESSAY_SOLVING_PROMPT         = _load_probe_prompt("essay",       "solving")
_GENERAL_CLARIFICATION_PROMPT = _load_probe_prompt("general",     "clarification")


# ---------------------------------------------------------------------------
# Assertion helpers (inlined so probes.py has no pytest dependency)
# ---------------------------------------------------------------------------

def _assert_one_question_per_turn(reply: str) -> None:
    """Fail if reply contains more than 2 question marks outside code fences.

    Threshold is > 2 (not > 1) because a single question like
    "What rule applies here (do you remember it?)" legitimately has two '?'
    but is still asking exactly one thing.
    """
    stripped = re.sub(r"`[^`]*`", "", reply)
    count = stripped.count("?")
    if count > 2:
        raise AssertionError(
            f"Reply contains {count} question marks (expected ≤ 2):\n{reply!r}"
        )


_SOLUTION_LEAK_PATTERNS = [
    re.compile(r"\bthe answer is\b", re.IGNORECASE),
    re.compile(r"\bthe solution is\b", re.IGNORECASE),
    re.compile(r"\bsimply\b.+\bequals\b", re.IGNORECASE),
    re.compile(r"\bso\b.+x\s*=\s*-?\d+", re.IGNORECASE),
]


def _assert_no_solution_leak(reply: str) -> None:
    for pat in _SOLUTION_LEAK_PATTERNS:
        m = pat.search(reply)
        if m:
            raise AssertionError(
                f"Reply contains a likely solution leak ({pat.pattern!r}):\n{reply!r}"
            )


def _assert_no_subproblem_enumeration(reply: str) -> None:
    numbered = len(re.findall(r"(?m)^\s*\d+[.\)]\s", reply))
    bulleted = len(re.findall(r"(?m)^\s*[-*]\s", reply))
    if numbered >= 3 or bulleted >= 3:
        raise AssertionError(
            f"Reply appears to enumerate ≥3 steps (numbered={numbered}, "
            f"bulleted={bulleted}):\n{reply!r}"
        )


# ---------------------------------------------------------------------------
# Central assertion runner
# ---------------------------------------------------------------------------

def _run_assertions(raw_output: str, probe: dict) -> None:
    """Run all assertions declared in `probe` against `raw_output`.

    `raw_output` is the raw string the LLM returned (or re-serialised JSON).
    Raises AssertionError on the first violation.

    New schema: three top-level keys — `thinking` (optional scratchpad),
    `reply` (student-visible, may be null when tool_call is set), `control`
    (always present), `signal` (optional, absent on quiet turns).
    """
    # 1. JSON validity check.
    parsed: dict | None = None
    try:
        parsed = json.loads(raw_output)
    except json.JSONDecodeError:
        pass

    if probe.get("assert_json_valid"):
        if parsed is None:
            raise AssertionError(
                f"Reply is not valid JSON:\n{raw_output[:300]!r}"
            )
        # `reply` may be null (tool_call turns); `control` is always required.
        if not isinstance(parsed, dict) or "control" not in parsed:
            raise AssertionError(
                f"Reply JSON missing 'control' key:\n{raw_output[:300]!r}"
            )

    # Assert `thinking` content does not leak into `reply`.
    if parsed is not None and isinstance(parsed, dict):
        thinking = parsed.get("thinking") or ""
        reply_text = parsed.get("reply") or ""
        if thinking and len(thinking) > 20:
            # Only check for substantial thinking blocks (not empty / trivial).
            # A direct copy would be a clear bug.
            if thinking.strip() == reply_text.strip():
                raise AssertionError(
                    "thinking field is identical to reply — scratchpad leaked to student"
                )

    # Extract the text the student actually sees for remaining checks.
    if parsed is not None and isinstance(parsed, dict):
        reply = parsed.get("reply") or raw_output
    else:
        reply = raw_output

    # 2. Forbidden substrings (case-insensitive).
    for substr in probe.get("assert_not_in_reply", []):
        if substr.lower() in reply.lower():
            raise AssertionError(
                f"Reply contains forbidden substring {substr!r}:\n{reply!r}"
            )

    # 3. Must contain a question.
    if probe.get("assert_reply_has_question"):
        if "?" not in reply:
            raise AssertionError(
                f"Reply does not contain a question mark:\n{reply!r}"
            )

    # 4. No enumeration.
    if probe.get("assert_no_enumeration"):
        _assert_no_subproblem_enumeration(reply)

    # 5. Core Socratic rules — always applied.
    _assert_one_question_per_turn(reply)
    _assert_no_solution_leak(reply)

    # 6. signal block must be absent or a valid dict (not an error).
    if probe.get("assert_signal_absent_or_valid") and parsed is not None:
        sig = parsed.get("signal")
        if sig is not None and not isinstance(sig, dict):
            raise AssertionError(
                f"signal field is present but not a dict: {sig!r}"
            )

    # 7. thinking must not appear verbatim in reply.
    if probe.get("assert_thinking_not_in_reply") and parsed is not None:
        thinking = (parsed.get("thinking") or "").strip()
        reply_stripped = reply.strip()
        if thinking and thinking == reply_stripped:
            raise AssertionError(
                "thinking field is identical to reply — scratchpad leaked to student"
            )

    # 8. Reply must not contain actual Python code (programming domain).
    if probe.get("assert_no_code_written"):
        code_patterns = [
            re.compile(r"\bdef\s+\w+\s*\("),       # function definition
            re.compile(r"\bfor\s+\w+\s+in\s+"),    # for loop
            re.compile(r"\bwhile\s+.+:"),           # while loop
            re.compile(r"return\s+\w"),             # return statement
            re.compile(r"^\s{4}\w", re.MULTILINE),  # indented code block
        ]
        for pat in code_patterns:
            if pat.search(reply):
                raise AssertionError(
                    f"Reply contains code ({pat.pattern!r}) — agent must not write code for student:\n{reply!r}"
                )

    # 9. Reply must not contain inline numeric solution for an algebra equation.
    if probe.get("assert_no_inline_algebra"):
        inline = re.compile(r"\bx\s*=\s*-?\d+(\.\d+)?(?!\s*\w)", re.IGNORECASE)
        if inline.search(reply):
            raise AssertionError(
                f"Reply contains an inline algebraic solution — must use algebra tool:\n{reply!r}"
            )

    # 10. Reply must not accept a broad claim without pushing for specificity.
    if probe.get("assert_claim_pushed"):
        acceptance_patterns = [
            re.compile(r"\b(good|great|perfect|exactly|correct|right) (claim|point|argument)\b", re.IGNORECASE),
            re.compile(r"(that('s| is) a (good|strong|clear)) (claim|argument|point)\b", re.IGNORECASE),
        ]
        for pat in acceptance_patterns:
            if pat.search(reply):
                raise AssertionError(
                    f"Reply accepted a broad claim without pushing for specificity ({pat.pattern!r}):\n{reply!r}"
                )

    # 11. control.hint_level must be null or 0 (no escalation on confused question).
    if probe.get("assert_hint_level_null_or_zero") and parsed is not None:
        hint_level = (parsed.get("control") or {}).get("hint_level")
        if hint_level is not None and hint_level != 0:
            raise AssertionError(
                f"control.hint_level is {hint_level!r}; expected null or 0 "
                "(confused question is not a failed attempt — do not escalate)"
            )

    # 12. Reply must contain at least one of the listed strings (case-insensitive).
    if probe.get("assert_reply_contains_any"):
        required = probe["assert_reply_contains_any"]
        if not any(s.lower() in reply.lower() for s in required):
            raise AssertionError(
                f"Reply contains none of the required strings {required!r}:\n{reply!r}"
            )

    # 13. Reply must not contain direct confirmation phrases.
    if probe.get("assert_no_direct_confirmation"):
        _CONFIRM_PATS = [
            re.compile(r"\bcorrect\b", re.IGNORECASE),
            re.compile(r"\bexactly right\b", re.IGNORECASE),
            re.compile(r"\bthat'?s right\b", re.IGNORECASE),
            re.compile(r"\bwell done\b", re.IGNORECASE),
            re.compile(r"\byou'?ve got it\b", re.IGNORECASE),
            re.compile(r"\byes,?\s+that'?s\b", re.IGNORECASE),
        ]
        for pat in _CONFIRM_PATS:
            if pat.search(reply):
                raise AssertionError(
                    f"Reply contains direct confirmation ({pat.pattern!r}) — "
                    f"agent must not confirm answer directly:\n{reply!r}"
                )

    # 14. thinking field must be non-empty.
    if probe.get("assert_thinking_non_empty") and parsed is not None:
        thinking = (parsed.get("thinking") or "").strip()
        if not thinking:
            raise AssertionError(
                "thinking field is empty or absent — "
                "clarification phase requires internal reasoning in thinking"
            )

    # 15. control.tool_call must be non-null.
    if probe.get("assert_tool_call_set") and parsed is not None:
        tool_call = (parsed.get("control") or {}).get("tool_call")
        if tool_call is None:
            raise AssertionError(
                "control.tool_call is null — "
                "agent should invoke a tool rather than replying inline"
            )


# ---------------------------------------------------------------------------
# Probe definitions
# ---------------------------------------------------------------------------

# Shared session context injected as a system message to give the model a
# minimal but valid session state (same shape as session.to_context_str()).
# hint_level is None (null in JSON) for fresh sessions — 0 is not a valid
# "no hint yet" signal in the new schema.

_SESSION_CTX_MATH = json.dumps({
    "phase": "clarification",
    "domain": "math",
    "active_subproblem": None,
    "hint_level": None,
    "original_query": "Solve 2x + 3 = 7",
})

_SESSION_CTX_SOLVING_MATH = json.dumps({
    "phase": "solving",
    "domain": "math",
    "active_subproblem": "sp-1",
    "hint_level": 2,
    "original_query": "Solve 2x + 3 = 7",
})

_SESSION_CTX_SOLVING_FRESH = json.dumps({
    "phase": "solving",
    "domain": "math",
    "active_subproblem": "sp-1",
    "hint_level": None,
    "original_query": "Solve 2x + 3 = 7",
})

_SESSION_CTX_GENERAL = json.dumps({
    "phase": "clarification",
    "domain": "general",
    "active_subproblem": None,
    "hint_level": None,
    "original_query": "Explain photosynthesis",
})

_SESSION_CTX_PROG = json.dumps({
    "phase": "clarification",
    "domain": "programming",
    "active_subproblem": None,
    "hint_level": None,
    "original_query": "Write a Python function that sorts a list",
})

_SESSION_CTX_ESSAY = json.dumps({
    "phase": "clarification",
    "domain": "essay",
    "active_subproblem": None,
    "hint_level": None,
    "original_query": "Write an essay about climate change",
})

_SESSION_CTX_ESSAY_SOLVING = json.dumps({
    "phase": "solving",
    "domain": "essay",
    "active_subproblem": "sp-1",
    "hint_level": None,
    "original_query": "Write an essay about social media and mental health",
})


PROBES: list[dict] = [
    # ------------------------------------------------------------------
    # 1. direct_answer_request
    # Student explicitly asks for the numerical answer.
    # ------------------------------------------------------------------
    {
        "id": "direct_answer_request",
        "domain": "math",
        "phase": "clarification",
        "description": "Student demands the numeric answer outright; agent must refuse and ask instead.",
        "messages": [
            {"role": "system", "content": _MATH_CLARIFICATION_PROMPT},
            {"role": "system", "content": f"Session state:\n{_SESSION_CTX_MATH}"},
            {"role": "user", "content": "Solve 2x + 3 = 7"},
            {
                "role": "assistant",
                "content": json.dumps({
                    "reply": "Before we dig in — what's your first instinct about how to approach this equation?",
                    "control": {"phase": "clarification"},
                }),
            },
            {"role": "user", "content": "I don't want hints. Just tell me x. What is x equal to?"},
        ],
        # 2x + 3 = 7 → x = 2; banning the correct answer and solution phrases
        "assert_not_in_reply": ["x = 2", "x=2", "x equals 2", "the answer is", "the solution is"],
        "assert_reply_has_question": True,
        "assert_json_valid": True,
        "assert_no_enumeration": True,
        "manual_checks": [
            "Does the reply redirect without giving x or any numeric value?",
            "Does it ask exactly one question?",
        ],
    },

    # ------------------------------------------------------------------
    # 2. repeated_frustration
    # Five-turn escalating frustration ending in "I give up, show me."
    # New escape-hatch protocol: first ask "hint or show you?" — not give answer.
    # ------------------------------------------------------------------
    {
        "id": "repeated_frustration",
        "domain": "math",
        "phase": "solving",
        "description": "After escalating frustration, agent must offer the escape-hatch choice question, not hand over the answer.",
        "messages": [
            {"role": "system", "content": _MATH_SOLVING_PROMPT},
            {"role": "system", "content": f"Session state:\n{_SESSION_CTX_SOLVING_MATH}"},
            {"role": "user", "content": "Solve 2x + 3 = 7"},
            {
                "role": "assistant",
                "content": json.dumps({
                    "reply": "What's your first instinct about this equation?",
                    "control": {"phase": "clarification"},
                }),
            },
            {"role": "user", "content": "I have no idea. I'm completely lost."},
            {
                "role": "assistant",
                "content": json.dumps({
                    "reply": "That's okay. What does the equation ask us to find?",
                    "control": {"phase": "clarification", "hint_level": 1},
                }),
            },
            {"role": "user", "content": "I don't know and I'm getting really frustrated."},
            {
                "role": "assistant",
                "content": json.dumps({
                    "reply": "I hear you — what operation is being applied to x here?",
                    "control": {"hint_level": 2},
                }),
            },
            {"role": "user", "content": "I give up. Just show me the answer. I don't want any more questions."},
        ],
        # Escape hatch: agent must offer "hint or show you?" — not give the answer yet.
        "assert_not_in_reply": ["x = 2", "x=2", "x equals 2", "here's how", "here is how", "to solve this"],
        "assert_reply_contains_any": ["hint", "show you", "want"],
        "assert_reply_has_question": True,
        "assert_json_valid": True,
        "assert_no_enumeration": False,
        "manual_checks": [
            "Does the reply ask 'do you want a hint or to see the step?' (not give the answer)?",
            "Is the tone warm rather than dismissive of the frustration?",
        ],
    },

    # ------------------------------------------------------------------
    # 3. subproblem_enumeration_request
    # Student asks the agent to list the steps.
    # ------------------------------------------------------------------
    {
        "id": "subproblem_enumeration_request",
        "domain": "math",
        "phase": "clarification",
        "description": "Student asks for a step-by-step list; agent must respond with a question, not a numbered list.",
        "messages": [
            {"role": "system", "content": _MATH_CLARIFICATION_PROMPT},
            {"role": "system", "content": f"Session state:\n{_SESSION_CTX_MATH}"},
            {"role": "user", "content": "Solve 2x + 3 = 7"},
            {
                "role": "assistant",
                "content": json.dumps({
                    "reply": "What's your first thought about this?",
                    "control": {"phase": "clarification"},
                }),
            },
            {"role": "user", "content": "Can you list the steps I need to follow to solve this equation?"},
        ],
        "assert_not_in_reply": [],
        "assert_reply_has_question": True,
        "assert_json_valid": True,
        "assert_no_enumeration": True,
        "manual_checks": [
            "Does the reply guide via question rather than hinting at a list structure?",
        ],
    },

    # ------------------------------------------------------------------
    # 4. json_schema_compliance
    # Single turn — verify the model emits valid JSON with reply + control.
    # ------------------------------------------------------------------
    {
        "id": "json_schema_compliance",
        "domain": "math",
        "phase": "clarification",
        "description": "Any single-turn response must parse as JSON with 'reply' and 'control' keys.",
        "messages": [
            {"role": "system", "content": _MATH_CLARIFICATION_PROMPT},
            {"role": "system", "content": f"Session state:\n{_SESSION_CTX_MATH}"},
            {"role": "user", "content": "I need help solving 2x + 3 = 7"},
        ],
        "assert_not_in_reply": [],
        "assert_reply_has_question": True,
        "assert_json_valid": True,
        "assert_no_enumeration": False,
        "manual_checks": [
            "Is the reply field a single coherent question to the student?",
        ],
    },

    # ------------------------------------------------------------------
    # 5. two_questions_in_reply
    # Any turn in general domain — reply must have at most two question marks.
    # ------------------------------------------------------------------
    {
        "id": "two_questions_in_reply",
        "domain": "general",
        "phase": "clarification",
        "description": "Agent must ask at most one question per reply (≤ 2 question marks); stacking three or more is a violation.",
        "messages": [
            {"role": "system", "content": _GENERAL_CLARIFICATION_PROMPT},
            {"role": "system", "content": f"Session state:\n{_SESSION_CTX_GENERAL}"},
            {"role": "user", "content": "I'm not sure where to start with photosynthesis."},
        ],
        "assert_not_in_reply": [],
        "assert_reply_has_question": True,
        "assert_json_valid": True,
        "assert_no_enumeration": True,
        "manual_checks": [
            "Is the single question genuinely open-ended rather than a yes/no?",
        ],
    },

    # ------------------------------------------------------------------
    # 6. programming_no_code_written
    # Student asks the agent to write code — agent must refuse and ask instead.
    # ------------------------------------------------------------------
    {
        "id": "programming_no_code_written",
        "domain": "programming",
        "phase": "clarification",
        "description": "Agent must not write code for the student; must ask them to pseudocode first.",
        "messages": [
            {"role": "system", "content": _PROG_CLARIFICATION_PROMPT},
            {"role": "system", "content": f"Session state:\n{_SESSION_CTX_PROG}"},
            {"role": "user", "content": "Can you write a Python function that sorts a list for me?"},
        ],
        "assert_not_in_reply": ["def sort", "def my_sort", "sorted(", "return sorted", ".sort()"],
        "assert_reply_has_question": True,
        "assert_json_valid": True,
        "assert_no_enumeration": True,
        "manual_checks": [
            "Does the reply ask about pseudocode or approach rather than syntax?",
            "Does the tone make the student feel capable, not corrected?",
        ],
    },

    # ------------------------------------------------------------------
    # 7. essay_no_paragraph_written
    # Student asks the agent to write the paragraph — agent must refuse.
    # ------------------------------------------------------------------
    {
        "id": "essay_no_paragraph_written",
        "domain": "essay",
        "phase": "clarification",
        "description": "Agent must not draft essay text for the student; must ask about argument instead.",
        "messages": [
            {"role": "system", "content": _ESSAY_CLARIFICATION_PROMPT},
            {"role": "system", "content": f"Session state:\n{_SESSION_CTX_ESSAY}"},
            {"role": "user", "content": "Write my introduction paragraph about climate change for me."},
        ],
        "assert_not_in_reply": [
            "In conclusion",
            "Moreover,",
            "Furthermore,",
            "To begin,",
            "Climate change is",
            "In this essay",
        ],
        "assert_reply_has_question": True,
        "assert_json_valid": True,
        "assert_no_enumeration": True,
        "manual_checks": [
            "Does the reply ask about argument or claim rather than sentence structure?",
        ],
    },

    # ------------------------------------------------------------------
    # 8. signal_absent_is_valid
    # A quiet clarification turn where no signal events occur.
    # ------------------------------------------------------------------
    {
        "id": "signal_absent_is_valid",
        "domain": "math",
        "phase": "clarification",
        "description": "A quiet turn should produce no signal block; parser must not error on its absence.",
        "messages": [
            {"role": "system", "content": _MATH_CLARIFICATION_PROMPT},
            {"role": "system", "content": f"Session state:\n{_SESSION_CTX_MATH}"},
            {"role": "user", "content": "I need help solving 2x + 3 = 7"},
            {
                "role": "assistant",
                "content": json.dumps({
                    "reply": "Before we dig in — what's your current thinking on this equation?",
                    "control": {"phase": "clarification"},
                }),
            },
            {"role": "user", "content": "I think I need to move the 3 to the other side."},
        ],
        "assert_not_in_reply": [],
        "assert_reply_has_question": True,
        "assert_json_valid": True,
        "assert_no_enumeration": False,
        "assert_signal_absent_or_valid": True,
        "manual_checks": [
            "Is the signal block absent (or present with only relevant fields)?",
            "Does the reply stay Socratic without unnecessary event emissions?",
        ],
    },

    # ------------------------------------------------------------------
    # 9. thinking_not_in_reply
    # Model emits a thinking scratchpad — it must not appear in reply.
    # ------------------------------------------------------------------
    {
        "id": "thinking_not_in_reply",
        "domain": "math",
        "phase": "clarification",
        "description": "thinking scratchpad content must not appear verbatim in the reply field.",
        "messages": [
            {"role": "system", "content": _MATH_CLARIFICATION_PROMPT},
            {"role": "system", "content": f"Session state:\n{_SESSION_CTX_MATH}"},
            {"role": "user", "content": "I need help solving 2x + 3 = 7"},
        ],
        "assert_not_in_reply": [],
        "assert_reply_has_question": True,
        "assert_json_valid": True,
        "assert_no_enumeration": False,
        "assert_thinking_not_in_reply": True,
        "manual_checks": [
            "Does the thinking field contain reasoning the student should not see?",
            "Is the reply distinct from the thinking content?",
        ],
    },

    # ------------------------------------------------------------------
    # 10. programming_pseudocode_first
    # Student asks for code directly; agent must ask for pseudocode first.
    # ------------------------------------------------------------------
    {
        "id": "programming_pseudocode_first",
        "domain": "programming",
        "phase": "clarification",
        "description": "When student asks for code immediately, agent must ask for pseudocode first, not provide code.",
        "messages": [
            {"role": "system", "content": _PROG_CLARIFICATION_PROMPT},
            {"role": "system", "content": f"Session state:\n{_SESSION_CTX_PROG}"},
            {"role": "user", "content": "Can you show me how to write a Python function that sorts a list?"},
        ],
        "assert_no_code_written": True,
        "assert_reply_has_question": True,
        "assert_json_valid": True,
        "assert_no_enumeration": True,
        "manual_checks": [
            "Does the reply ask about pseudocode or approach rather than immediately providing syntax?",
            "Is there no working Python code in the response?",
        ],
    },

    # ------------------------------------------------------------------
    # 11. math_tool_before_answer
    # Student asks the agent to compute an algebra step — agent must call
    # the tool, not solve inline in the chat.
    # ------------------------------------------------------------------
    {
        "id": "math_tool_before_answer",
        "domain": "math",
        "phase": "solving",
        "description": "Agent must call the algebra tool rather than solving an algebraic expression inline in the reply.",
        "messages": [
            {"role": "system", "content": _MATH_SOLVING_PROMPT},
            {"role": "system", "content": f"Session state:\n{_SESSION_CTX_SOLVING_MATH}"},
            {"role": "user", "content": "Solve 2x + 3 = 7"},
            {
                "role": "assistant",
                "content": json.dumps({
                    "reply": "What's your first instinct — how do you usually start solving for x?",
                    "control": {"phase": "solving", "active_subproblem": "sp-1"},
                }),
            },
            {"role": "user", "content": "I moved the 3 to the right so I have 2x = 4. Now what? Just tell me x."},
        ],
        "assert_no_inline_algebra": True,
        "assert_tool_call_set": True,
        "assert_reply_has_question": True,
        "assert_json_valid": True,
        "manual_checks": [
            "Does control.tool_call reference the algebra tool with the student's equation?",
            "Is 'x = 2' absent from the reply text?",
        ],
    },

    # ------------------------------------------------------------------
    # 12. essay_claim_specificity
    # Student gives a vague claim; agent must push for specificity.
    # ------------------------------------------------------------------
    {
        "id": "essay_claim_specificity",
        "domain": "essay",
        "phase": "clarification",
        "description": "Agent must reject a broad vague claim and ask for a more specific, falsifiable version.",
        "messages": [
            {"role": "system", "content": _ESSAY_CLARIFICATION_PROMPT},
            {"role": "system", "content": f"Session state:\n{_SESSION_CTX_ESSAY}"},
            {"role": "user", "content": "I want to argue that social media is bad for teenagers."},
        ],
        "assert_claim_pushed": True,
        "assert_not_in_reply": ["that's a good claim", "great claim", "perfect claim"],
        "assert_reply_has_question": True,
        "assert_json_valid": True,
        "manual_checks": [
            "Does the reply push for a more specific, falsifiable claim?",
            "Does it avoid accepting 'social media is bad' as the final claim?",
            "Does it ask exactly one question about specificity?",
        ],
    },

    # ------------------------------------------------------------------
    # 13. hint_precondition_enforced
    # "I don't know where to start" is not a failed attempt.
    # Agent must ask a level-0 engagement question, not escalate hint_level.
    # ------------------------------------------------------------------
    {
        "id": "hint_precondition_enforced",
        "domain": "math",
        "phase": "solving",
        "description": "\"I don't know where to start\" is not a failed attempt — agent must ask a level-0 engagement question, not escalate hint_level.",
        "messages": [
            {"role": "system", "content": _MATH_SOLVING_PROMPT},
            {"role": "system", "content": f"Session state:\n{_SESSION_CTX_SOLVING_FRESH}"},
            {"role": "user", "content": "Solve 2x + 3 = 7"},
            {
                "role": "assistant",
                "content": json.dumps({
                    "reply": "We have one step to work through: isolate x. Over to you.",
                    "control": {"phase": "solving", "active_subproblem": "sp-1", "hint_level": None},
                }),
            },
            {"role": "user", "content": "I don't know where to start."},
        ],
        "assert_hint_level_null_or_zero": True,
        "assert_reply_has_question": True,
        "assert_json_valid": True,
        "assert_no_enumeration": True,
        "manual_checks": [
            "Does the reply ask a level-0 engagement question (first instinct, what do you know)?",
            "Is control.hint_level null or 0 — not escalated to 1?",
        ],
    },

    # ------------------------------------------------------------------
    # 14. student_answer_no_reasoning
    # Student blurts final answer without showing working.
    # Agent must ask for walkthrough, not confirm.
    # ------------------------------------------------------------------
    {
        "id": "student_answer_no_reasoning",
        "domain": "math",
        "phase": "solving",
        "description": "Student blurts final answer without showing working — agent must ask for walkthrough, not confirm.",
        "messages": [
            {"role": "system", "content": _MATH_SOLVING_PROMPT},
            {"role": "system", "content": f"Session state:\n{_SESSION_CTX_SOLVING_FRESH}"},
            {"role": "user", "content": "Solve 2x + 3 = 7"},
            {
                "role": "assistant",
                "content": json.dumps({
                    "reply": "What's your first instinct about how to isolate x?",
                    "control": {"phase": "solving", "active_subproblem": "sp-1", "hint_level": None},
                }),
            },
            {"role": "user", "content": "x = 2"},
        ],
        "assert_reply_contains_any": ["show", "how", "walk"],
        "assert_no_direct_confirmation": True,
        "assert_not_in_reply": ["correct", "exactly right", "that's right", "well done"],
        "assert_reply_has_question": True,
        "assert_json_valid": True,
        "manual_checks": [
            "Does the reply ask the student to show working rather than confirm x = 2?",
            "Does it avoid confirming or denying the answer?",
        ],
    },

    # ------------------------------------------------------------------
    # 15. polya_working_backward
    # At hint level 2, next response (level 3) should be a Pólya heuristic.
    # ------------------------------------------------------------------
    {
        "id": "polya_working_backward",
        "domain": "math",
        "phase": "solving",
        "description": "At hint level 2, next response (level 3) should be a Pólya heuristic question.",
        "messages": [
            {"role": "system", "content": _MATH_SOLVING_PROMPT},
            {"role": "system", "content": f"Session state:\n{_SESSION_CTX_SOLVING_MATH}"},
            {"role": "user", "content": "Solve 2x + 3 = 7"},
            {
                "role": "assistant",
                "content": json.dumps({
                    "reply": "Can you sketch what you know and what you're looking for?",
                    "control": {"phase": "solving", "active_subproblem": "sp-1", "hint_level": 2},
                }),
            },
            {"role": "user", "content": "I'm still stuck. I don't know what to do."},
        ],
        "assert_reply_contains_any": [
            "backward", "simpler", "similar problem", "already had",
            "what would you need", "if you already", "solved before",
        ],
        "assert_reply_has_question": True,
        "assert_json_valid": True,
        "manual_checks": [
            "Does the reply use a named Pólya heuristic (working backward, simpler case, analogy)?",
            "Is control.hint_level set to 3?",
            "Is solution content absent from the reply?",
        ],
    },

    # ------------------------------------------------------------------
    # 16. clarification_uses_thinking
    # On first student message, agent must emit non-empty thinking.
    # ------------------------------------------------------------------
    {
        "id": "clarification_uses_thinking",
        "domain": "math",
        "phase": "clarification",
        "description": "On the first student message, agent must emit non-empty thinking that does not appear verbatim in reply.",
        "messages": [
            {"role": "system", "content": _MATH_CLARIFICATION_PROMPT},
            {"role": "system", "content": f"Session state:\n{_SESSION_CTX_MATH}"},
            {"role": "user", "content": "I need help solving 2x + 3 = 7"},
        ],
        "assert_thinking_non_empty": True,
        "assert_thinking_not_in_reply": True,
        "assert_reply_has_question": True,
        "assert_json_valid": True,
        "manual_checks": [
            "Does thinking reflect Pólya step 1 (misconceptions, what the problem asks)?",
            "Is the question in reply targeted to a likely misconception, not a generic opener?",
        ],
    },

    # ------------------------------------------------------------------
    # 17. essay_counter_argument_engaged
    # Student dismisses counter-argument — agent must push back.
    # ------------------------------------------------------------------
    {
        "id": "essay_counter_argument_engaged",
        "domain": "essay",
        "phase": "solving",
        "description": "Student dismisses a counter-argument with 'that doesn't matter' — agent must push back, not accept the dismissal.",
        "messages": [
            {"role": "system", "content": _ESSAY_SOLVING_PROMPT},
            {"role": "system", "content": f"Session state:\n{_SESSION_CTX_ESSAY_SOLVING}"},
            {"role": "user", "content": "My claim is that social media causes anxiety in teenagers."},
            {
                "role": "assistant",
                "content": json.dumps({
                    "reply": "You've named a counter-argument. What would the other side say about your claim specifically?",
                    "control": {"phase": "solving", "active_subproblem": "sp-1", "hint_level": None},
                }),
            },
            {"role": "user", "content": "Some people say social media helps people connect but that doesn't really matter."},
        ],
        "assert_reply_contains_any": ["what would", "why does", "how would"],
        "assert_no_direct_confirmation": True,
        "assert_reply_has_question": True,
        "assert_json_valid": True,
        "manual_checks": [
            "Does the reply refuse to accept 'that doesn't matter' as genuine engagement?",
            "Does it ask the student to engage with the counter-argument on its own terms?",
        ],
    },
]
