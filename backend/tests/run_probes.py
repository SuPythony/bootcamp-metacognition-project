"""Manual probe runner.

Usage (from the backend/ directory):
    python -m tests.run_probes
    python -m tests.run_probes --probe json_schema_compliance
    python -m tests.run_probes --model google/gemini-2.5-flash
    python -m tests.run_probes --base-variant base:v1 --domain-variant math:v1

Reads LLM_MODEL_TUTOR from env (overridable via --model).
Reads PROBE_TEMPERATURE from env (default 0.3).

Exits with code 1 if any probe fails, so CI can gate on it.
Results are also written to backend/logs/probe_runs.jsonl.

The runner calls llm.py directly — the FastAPI server does NOT need to be running.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import os
import re
import sys
import time
from pathlib import Path

# Ensure the backend package is importable when run as `python -m tests.run_probes`
# from the backend/ directory, or via a bare `python tests/run_probes.py`.
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app import llm  # noqa: E402
from app.prompts.variants import parse_domain_variants  # noqa: E402
from tests.probes import PROBES, _run_assertions, _load_probe_prompt  # noqa: E402


def _logs_dir() -> Path:
    d = _BACKEND / "logs"
    d.mkdir(exist_ok=True)
    return d


def _write_probe_log(result: dict) -> None:
    log_path = _logs_dir() / "probe_runs.jsonl"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(result) + "\n")


def _rebuild_probe_messages(
    probe: dict,
    base_variant: str | None,
    domain_variant_arg: str | None,
) -> list[dict]:
    """Return probe messages with messages[0] replaced by the requested variant combo.

    `domain_variant_arg` is the raw --domain-variant string, either a single key
    ("math:v2") or a comma-separated map ("math:v2,essay:v1"). The probe's domain
    is used to look up the right key; if the domain isn't in the map the default
    is used (None → load_combined falls back to the registry default).
    """
    domain_map = parse_domain_variants(domain_variant_arg or "")
    domain_variant = domain_map.get(probe["domain"])
    phase = probe.get("phase", "clarification")
    messages = list(probe["messages"])
    messages[0] = dict(messages[0])
    messages[0]["content"] = _load_probe_prompt(
        probe["domain"], phase, base_variant, domain_variant
    )
    return messages


def _extract_reply_preview(raw_preview: str) -> str | None:
    """Return a formatted first/last-sentence quote of the reply field."""
    try:
        obj = json.loads(raw_preview)
        reply = obj.get("reply", "") if isinstance(obj, dict) else ""
    except json.JSONDecodeError:
        reply = raw_preview
    if not reply:
        return None

    reply = reply.strip()
    delimiters = [m.start() for m in re.finditer(r"[.!?]", reply)]

    if not delimiters:
        return f'"{reply}"'

    first = reply[: delimiters[0] + 1].strip()

    # Last complete sentence: text between the second-to-last and last delimiter.
    last_start = delimiters[-1] + 1
    last = reply[last_start:].strip()
    if not last and len(delimiters) >= 2:
        last = reply[delimiters[-2] + 1 : delimiters[-1] + 1].strip()

    if not last or last == first:
        return f'"{first}"'
    return f'"{first} … ({last})"'


async def _run_one(
    probe: dict,
    temperature: float,
    base_variant: str | None = None,
    domain_variant: str | None = None,
) -> dict:
    """Run a single probe against the real LLM. Returns a result dict."""
    t0 = time.monotonic()
    failure_reason: str | None = None
    raw_output: str = ""

    messages = (
        _rebuild_probe_messages(probe, base_variant, domain_variant)
        if (base_variant or domain_variant)
        else probe["messages"]
    )

    try:
        raw_dict, _ = await llm.call_tutor(
            messages,
            temperature=temperature,
            session_id="probe-runner",
        )
        raw_output = json.dumps(raw_dict)
        _run_assertions(raw_output, probe)
    except llm.LLMError as e:
        failure_reason = f"LLMError: {e}"
    except AssertionError as e:
        failure_reason = str(e)

    latency_ms = int((time.monotonic() - t0) * 1000)
    passed = failure_reason is None

    return {
        "probe_id": probe["id"],
        "passed": passed,
        "latency_ms": latency_ms,
        "failure_reason": failure_reason,
        "raw_output_preview": raw_output[:300] if raw_output else "",
        "base_variant": base_variant,
        "domain_variant": domain_variant,
        "ts":  datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


def _print_result(result: dict, probe: dict) -> None:
    status = "\033[92m[PASS]\033[0m" if result["passed"] else "\033[91m[FAIL]\033[0m"
    print(f"{status} {result['probe_id']:<40} ({result['latency_ms']}ms)")

    if not result["passed"]:
        reason_lines = result["failure_reason"].splitlines()
        for line in reason_lines[:5]:
            print(f"       {line}")

    # Reply preview — always shown so reviewers can judge pedagogy without opening logs.
    if result["raw_output_preview"]:
        preview = _extract_reply_preview(result["raw_output_preview"])
        if preview:
            print(f"       reply: {preview}")

    # Manual checks — printed for ALL probes in bold yellow.
    for check in probe.get("manual_checks", []):
        print(f"       \033[1;33m[MANUAL] {check}\033[0m")


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run Socratic discipline probes against the real LLM.")
    parser.add_argument("--model", default=None, help="Override LLM_MODEL_TUTOR env var.")
    parser.add_argument("--probe", default=None, help="Run only the probe with this id.")
    parser.add_argument(
        "--base-variant", default=None, dest="base_variant",
        help="Base prompt variant key to use (e.g. base:v1).",
    )
    parser.add_argument(
        "--domain-variant", default=None, dest="domain_variant",
        help="Domain prompt variant key to use (e.g. math:v1).",
    )
    args = parser.parse_args()

    if args.model:
        os.environ["LLM_MODEL_TUTOR"] = args.model

    temperature = float(os.environ.get("PROBE_TEMPERATURE", "0.3"))
    base_variant: str | None = args.base_variant
    domain_variant: str | None = args.domain_variant

    probes_to_run = PROBES
    if args.probe:
        probes_to_run = [p for p in PROBES if p["id"] == args.probe]
        if not probes_to_run:
            ids = ", ".join(p["id"] for p in PROBES)
            print(f"Unknown probe id {args.probe!r}. Available: {ids}", file=sys.stderr)
            return 1

    base_label = base_variant or "base:v1"
    domain_label = domain_variant or "<probe-domain>:v1"
    print(f"Running {len(probes_to_run)} probes | base={base_label} domain={domain_label} | temp={temperature}")

    results = []
    for probe in probes_to_run:
        result = await _run_one(
            probe, temperature,
            base_variant=base_variant,
            domain_variant=domain_variant,
        )
        _print_result(result, probe)
        _write_probe_log(result)
        results.append(result)

    passed = sum(1 for r in results if r["passed"])
    failed = len(results) - passed
    print(f"---\n{len(results)} probes | \033[92m{passed} passed\033[0m | \033[91m{failed} failed\033[0m")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
