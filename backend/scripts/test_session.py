#!/usr/bin/env python3
"""
Interactive backend testing script for the Socratic Tutor.

Starts a session against a running backend and lets you chat turn-by-turn.
Every request, response, and session-state snapshot is logged to a JSON file.

Usage
-----
Interactive REPL (default):
    python scripts/test_session.py --query "solve 2x + 3 = 7"

Scripted (run a fixed message list then exit):
    python scripts/test_session.py --query "solve 2x + 3 = 7" \\
        --messages "I think x=2" "not sure about the second step" "give me a hint"

Options
-------
  --query      -q   Student problem (required)
  --username   -u   Persona username  [default: tester]
  --messages   -m   Space-separated messages for scripted mode
  --api-url        Backend base URL  [default: http://localhost:8000]
  --log-dir        Directory for log files  [default: logs/]
  --no-color       Disable ANSI colour output
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# ANSI colour helpers
# ---------------------------------------------------------------------------

_COLOURS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "cyan": "\033[36m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "red": "\033[31m",
    "magenta": "\033[35m",
    "blue": "\033[34m",
}

_use_colour = True


def c(text: str, *codes: str) -> str:
    if not _use_colour:
        return text
    prefix = "".join(_COLOURS[code] for code in codes)
    return f"{prefix}{text}{_COLOURS['reset']}"


# ---------------------------------------------------------------------------
# Pretty-print helpers
# ---------------------------------------------------------------------------

WIDTH = 78


def _hr(char: str = "─") -> str:
    return c(char * WIDTH, "dim")


def _wrap(text: str, indent: int = 0) -> str:
    prefix = " " * indent
    return textwrap.fill(text, width=WIDTH, initial_indent=prefix, subsequent_indent=prefix)


def print_banner(session_id: str, domain: str, username: str) -> None:
    print()
    print(_hr("═"))
    print(c(f"  Session  {session_id}", "bold", "cyan"))
    print(c(f"  Domain   {domain}  │  User: {username}", "dim"))
    print(_hr("═"))


def print_agent(reply: str, phase: str, subproblems: list[dict], ui_directives: list[dict]) -> None:
    print()
    print(c(f"  ▶ TUTOR  [{phase}]", "bold", "green"))
    print(_hr())
    for line in reply.splitlines():
        print(_wrap(line, indent=4) if line.strip() else "")
    if subproblems:
        print()
        print(c("  Subproblems:", "bold"))
        for sp in subproblems:
            status_col = {"pending": "dim", "active": "yellow", "solved": "green"}.get(sp.get("status", ""), "dim")
            hints = sp.get("hints_given", 0)
            hint_str = f" [{hints} hint{'s' if hints != 1 else ''}]" if hints else ""
            print(c(f"    {sp['id']}  {sp.get('status','?')}  —  {sp.get('description','')}{hint_str}", status_col))
    if ui_directives:
        print()
        print(c("  UI Directives:", "bold"))
        for d in ui_directives:
            print(c(f"    {d.get('component','?')} ({d.get('placement','?')})", "magenta"))
    print(_hr())


def print_user(message: str, turn: int) -> None:
    print()
    print(c(f"  ◀ YOU  [turn {turn}]", "bold", "blue"))
    print(_hr())
    print(_wrap(message, indent=4))


def print_error(msg: str) -> None:
    print(c(f"\n  ✗ {msg}", "red", "bold"), file=sys.stderr)


def print_info(msg: str) -> None:
    print(c(f"  · {msg}", "dim"))


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

class SessionLog:
    """Accumulates all request/response pairs and writes them to a JSON file."""

    def __init__(self, log_dir: Path, session_id: str, username: str, query: str, domain: str):
        log_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = f"{ts}_{domain}_{username}"
        self.path = log_dir / f"session_{slug}.json"
        self._data: dict = {
            "session_id": session_id,
            "username": username,
            "query": query,
            "domain": domain,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "ended_at": None,
            "turns": [],
        }
        self._flush()

    def record_turn(self, turn: int, request: dict, response: dict) -> None:
        self._data["turns"].append({
            "turn": turn,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request": request,
            "response": response,
        })
        self._flush()

    def close(self) -> None:
        self._data["ended_at"] = datetime.now(timezone.utc).isoformat()
        self._flush()
        print_info(f"Log saved → {self.path}")

    def _flush(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2, default=str))


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def new_session(client: httpx.Client, api_url: str, username: str, query: str) -> dict:
    resp = client.post(
        f"{api_url}/session/new",
        json={"username": username, "mode": "solving", "query": query},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def chat(client: httpx.Client, api_url: str, session_id: str, message: str) -> dict:
    resp = client.post(
        f"{api_url}/chat",
        json={"session_id": session_id, "message": message},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def thinking_trace(client: httpx.Client, api_url: str, session_id: str) -> dict:
    resp = client.get(f"{api_url}/session/{session_id}/thinking-trace", timeout=30)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Session runner
# ---------------------------------------------------------------------------

def run_session(
    api_url: str,
    username: str,
    query: str,
    messages: list[str] | None,
    log_dir: Path,
) -> None:
    with httpx.Client() as http:
        # --- Start session ---
        print_info(f"Connecting to {api_url} …")
        try:
            init = new_session(http, api_url, username, query)
        except httpx.ConnectError:
            print_error(f"Cannot reach {api_url}. Is the backend running?")
            sys.exit(1)
        except httpx.HTTPStatusError as e:
            print_error(f"Session creation failed: {e.response.status_code} {e.response.text}")
            sys.exit(1)

        session_id = init["session_id"]
        domain = init.get("domain", "unknown")
        opening = init.get("opening_message", "")

        log = SessionLog(log_dir, session_id, username, query, domain)
        log.record_turn(0, {"type": "session_new", "username": username, "query": query}, init)

        print_banner(session_id, domain, username)
        print_agent(opening, init.get("phase", "clarification"), [], [])

        turn = 1
        scripted = messages is not None
        msg_iter = iter(messages) if scripted else None

        while True:
            # --- Get next message ---
            if scripted:
                try:
                    user_msg = next(msg_iter)  # type: ignore[arg-type]
                except StopIteration:
                    break
            else:
                try:
                    print()
                    user_msg = input(c("  You: ", "bold", "blue")).strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    break
                if not user_msg:
                    continue
                if user_msg.lower() in {"/quit", "/exit", "/q"}:
                    break
                if user_msg.lower() in {"/trace", "/thinking"}:
                    try:
                        trace = thinking_trace(http, api_url, session_id)
                        print()
                        print(c("  Thinking Trace:", "bold", "cyan"))
                        print(_hr())
                        print(json.dumps(trace, indent=2))
                        print(_hr())
                    except Exception as exc:
                        print_error(f"Could not fetch thinking trace: {exc}")
                    continue
                if user_msg.lower() == "/help":
                    print(c("\n  Commands: /quit  /trace  /help\n", "dim"))
                    continue

            print_user(user_msg, turn)

            # --- Send to backend ---
            req_body = {"session_id": session_id, "message": user_msg}
            try:
                resp = chat(http, api_url, session_id, user_msg)
            except httpx.HTTPStatusError as e:
                print_error(f"Backend error {e.response.status_code}: {e.response.text}")
                log.record_turn(turn, req_body, {"error": e.response.text, "status_code": e.response.status_code})
                turn += 1
                continue
            except httpx.RequestError as e:
                print_error(f"Request failed: {e}")
                break

            log.record_turn(turn, req_body, resp)

            print_agent(
                resp.get("reply", ""),
                resp.get("phase", "?"),
                resp.get("subproblems", []),
                resp.get("ui_directives", []),
            )

            # Surface notable state changes
            if resp.get("frontend_tool_call"):
                tc = resp["frontend_tool_call"]
                print(c(f"  ⚡ Frontend tool requested: {tc.get('name')} (handler: {tc.get('frontend_handler')})", "yellow"))
            if resp.get("backend_tool_result"):
                tr = resp["backend_tool_result"]
                print(c(f"  ⚙  Backend tool ran: {tr.get('name')}", "green"))

            turn += 1

            # Auto-exit on wrap_up phase in scripted mode
            if scripted and resp.get("phase") == "wrap_up":
                print_info("Session reached wrap_up — stopping scripted run.")
                break

        # --- End of session ---
        print()
        print(_hr("═"))
        print(c("  Session ended.", "bold"))
        log.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Interactive Socratic Tutor backend tester",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--query", "-q", required=True, help="Student problem / opening message")
    parser.add_argument("--username", "-u", default="tester", help="Persona username [default: tester]")
    parser.add_argument(
        "--messages", "-m", nargs="+", metavar="MSG",
        help="Scripted messages to send in order, then exit (omit for interactive REPL)",
    )
    parser.add_argument("--api-url", default="http://localhost:8000", metavar="URL", help="Backend base URL")
    parser.add_argument("--log-dir", default="logs", metavar="DIR", help="Directory for JSON log files [default: logs/]")
    parser.add_argument("--no-colour", "--no-color", action="store_true", help="Disable ANSI colour output")

    args = parser.parse_args()

    global _use_colour
    _use_colour = not args.no_colour and sys.stdout.isatty()

    run_session(
        api_url=args.api_url.rstrip("/"),
        username=args.username,
        query=args.query,
        messages=args.messages,
        log_dir=Path(args.log_dir),
    )


if __name__ == "__main__":
    main()
