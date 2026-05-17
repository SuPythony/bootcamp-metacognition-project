#!/usr/bin/env python3
"""
Usage
-----
python log_viewer.py llm.jsonl

Optional:
python log_viewer.py llm.jsonl --host 0.0.0.0 --port 5000

Open:
http://127.0.0.1:5000

Dependencies
------------
pip install flask

LLM Log Viewer
--------------
Interactive viewer for JSONL LLM traces.

Features
--------
- Session + event filtering
- Collapsible parsed views
- Signal/control inspection
- Live refresh from file
- Readable + JSONL export

UI
--
- Left sidebar: filters
- Main pane: collapsible log cards
- Top bar: refresh + export
"""

import json
import argparse

from datetime import datetime
from flask import (
    Flask,
    render_template_string,
    request,
)

app = Flask(__name__)

LOGS = []
SESSIONS = []
EVENTS = []
LOG_PATH = None


HTML = r"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">

<title>LLM Log Viewer</title>

<style>

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    background: #0c0f14;
    color: #e6edf3;
    font-family: Inter, system-ui, sans-serif;
}

.layout {
    display: flex;
    height: 100vh;
}

.sidebar {
    width: 340px;
    border-right: 1px solid #232936;
    padding: 18px;
    overflow-y: auto;
    background: #11151c;
}

.main {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
}

h1 {
    margin-top: 0;
    font-size: 20px;
}

.topbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
}

.export-controls {
    display: flex;
    gap: 10px;
    align-items: center;
}

button {
    background: #1e293b;
    color: white;
    border: 1px solid #334155;
    padding: 8px 12px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 12px;
}

button:hover {
    background: #263449;
}

.filter-group {
    margin-bottom: 22px;
}

.filter-title {
    font-size: 12px;
    color: #9aa4b2;
    margin-bottom: 8px;
}

select {
    width: 100%;
    padding: 8px;
    border-radius: 8px;
    border: 1px solid #2d3748;
    background: #1a202c;
    color: white;
}

.event-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.event-chip {
    border: 1px solid #334155;
    background: #18202d;
    border-radius: 999px;
    padding: 6px 10px;
    font-size: 11px;
    cursor: pointer;
    user-select: none;
    transition: 0.12s ease;
}

.event-chip:hover {
    background: #243041;
}

.event-chip.selected {
    background: #2563eb;
    border-color: #3b82f6;
    color: white;
}

.small {
    color: #9aa4b2;
    font-size: 11px;
}

.log {
    margin-bottom: 14px;
    border: 1px solid #232936;
    border-radius: 12px;
    background: #121721;
    overflow: hidden;
}

.log > summary {
    cursor: pointer;
    list-style: none;
    padding: 12px 16px;
    background: #171d29;
    border-bottom: 1px solid #232936;
}

.log > summary::-webkit-details-marker {
    display: none;
}

.header-line {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
}

.badge {
    background: #283244;
    padding: 3px 7px;
    border-radius: 999px;
    font-size: 10px;
}

.session {
    color: #d6e4ff;
    font-weight: 700;
    font-size: 12px;
}

.callid {
    color: #8ea2c9;
    font-size: 11px;
}

.ts {
    color: #98a4b5;
    font-size: 11px;
}

.content {
    padding: 14px;
}

.meta-grid {
    display: flex;
    justify-content: space-between;
    margin-bottom: 12px;
}

.meta-left {
    display: flex;
    flex-direction: column;
    gap: 3px;
}

.meta-right {
    text-align: right;
}

.model {
    color: #42d392;
    font-weight: 800;
    font-size: 12px;
}

.latency {
    color: #ffd166;
    font-size: 11px;
}

.tokens {
    color: #9ecbff;
    font-size: 11px;
}

.parse {
    color: #b7c0ce;
    font-size: 11px;
}

.control-pill {
    border-radius: 999px;
    padding: 4px 8px;
    font-size: 10px;
    font-weight: 700;
    border: 1px solid transparent;
}

.phase-clarification {
    background: rgba(59,130,246,0.15);
    color: #93c5fd;
    border-color: rgba(59,130,246,0.4);
}

.phase-decomposition {
    background: rgba(168,85,247,0.15);
    color: #d8b4fe;
    border-color: rgba(168,85,247,0.4);
}

.phase-solving {
    background: rgba(34,197,94,0.15);
    color: #86efac;
    border-color: rgba(34,197,94,0.4);
}

.phase-wrap_up {
    background: rgba(245,158,11,0.15);
    color: #fcd34d;
    border-color: rgba(245,158,11,0.4);
}

.control-generic {
    background: #1b2432;
    color: #c7d2e0;
    border-color: #2d3748;
}

.section {
    margin-bottom: 10px;
    border: 1px solid #232936;
    border-radius: 8px;
    overflow: hidden;
}

.section > summary {
    cursor: pointer;
    padding: 7px 11px;
    background: #151b25;
    user-select: none;
    font-weight: 600;
    font-size: 12px;
}

.section-content {
    padding: 10px 12px;
    background: #0f141d;
}

pre {
    margin: 0;
    white-space: pre-wrap;
    word-break: break-word;
    line-height: 1.4;
    font-family: ui-monospace, monospace;
    font-size: 11px;
}

.signal-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 8px;
}

.signal-box {
    border: 1px solid #283244;
    border-radius: 8px;
    overflow: hidden;
    background: #141b26;
}

.signal-box summary {
    cursor: pointer;
    padding: 8px 10px;
    font-size: 11px;
    color: #a9c7ff;
    font-weight: 700;
}

.signal-box pre {
    padding: 10px;
    border-top: 1px solid #283244;
    background: #0f141d;
}

.export-checkbox {
    margin-right: 4px;
}

.auto-refresh {
    display: flex;
    align-items: center;
    gap: 6px;
    color: #9aa4b2;
    font-size: 11px;
    cursor: pointer;
    user-select: none;
}

.auto-refresh input {
    margin: 0;
    cursor: pointer;
}

#refreshStatus {
    color: #6b7785;
    font-size: 11px;
    min-width: 80px;
}

.hidden {
    display: none;
}

</style>
</head>

<body>

<div class="layout">

<div class="sidebar">

<h1>LLM Logs</h1>

<form method="GET" id="filterForm">

<div class="filter-group">

<div class="filter-title">
Session
</div>

<select name="session_id">

<option value="">
All Sessions
</option>

{% for s in sessions %}

<option
    value="{{s}}"
    {% if s == selected_session %}selected{% endif %}
>
{{s}}
</option>

{% endfor %}

</select>

</div>

<div class="filter-group">

<div class="filter-title">
Events
</div>

<div class="event-grid">

{% for e in events %}

<label
    class="event-chip {% if e in selected_events %}selected{% endif %}"
>

<input
    type="checkbox"
    name="event"
    value="{{e}}"
    class="hidden event-checkbox"

    {% if e in selected_events %}
    checked
    {% endif %}
>

{{e}}

</label>

{% endfor %}

</div>

</div>

<button type="submit">
Apply Filters
</button>

</form>

<div
    class="small"
    style="margin-top: 18px;"
>
Total: {{total}}
</div>

</div>

<div class="main">

<div class="topbar">

<div class="small">
Select logs to export
</div>

<div class="export-controls">

<label class="auto-refresh">
<input type="checkbox" id="autoRefreshToggle">
Auto-refresh (5s)
</label>

<span id="refreshStatus"></span>

<button type="button" onclick="refreshLogs()">
Refresh Logs
</button>

<button onclick="downloadReadable()">
Readable Export
</button>

<button onclick="downloadJsonl()">
JSONL Export
</button>

</div>

</div>

{% for log in logs %}

{% set parsed = parse_raw(log.get("raw_output")) %}

<details
    class="log"
    data-log-key="{{log.get('event','')}}|{{log.get('ts','')}}|{{log.get('call_id','')}}|{{loop.index}}"
>

<summary>

<div class="header-line">

<input
    type="checkbox"
    class="export-checkbox"
    data-log='{{json_dump(log)|safe}}'
>

<span class="badge">
{{log.get("event")}}
</span>

{% if log.get("session_id") %}
<span class="session">
{{log.get("session_id")}}
</span>
{% endif %}

{% if log.get("call_id") %}
<span class="callid">
{{log.get("call_id")}}
</span>
{% endif %}

<span class="ts">
{{human_ts(log.get("ts", ""))}}
</span>

{% if parsed and parsed.get("control") %}

{% for k, v in parsed.get("control", {}).items() %}

{% if v is not none %}

{% if k == "phase" %}
<span class="control-pill phase-{{v}}">
{{k}}: {{v}}
</span>
{% else %}
<span class="control-pill control-generic">
{{k}}: {{v}}
</span>
{% endif %}

{% endif %}

{% endfor %}

{% endif %}

</div>

</summary>

<div class="content">

<div class="meta-grid">

<div class="meta-left">

{% if log.get("latency_ms") %}
<div class="latency">
latency: {{log.get("latency_ms")}} ms
</div>
{% endif %}

{% if log.get("input_tokens") or log.get("output_tokens") %}
<div class="tokens">
in: {{log.get("input_tokens", "-")}}
|
out: {{log.get("output_tokens", "-")}}
</div>
{% endif %}

{% if log.get("parse_success") is not none %}
<div class="parse">
parse_success:
{{log.get("parse_success")}}
</div>
{% endif %}

</div>

<div class="meta-right">

{% if log.get("model") %}
<div class="model">
{{log.get("model")}}
</div>
{% endif %}

</div>

</div>

{% if parsed %}

<details class="section">

<summary>
thinking
</summary>

<div class="section-content">
<pre>{{parsed.get("thinking", "")}}</pre>
</div>

</details>

<details class="section" open>

<summary>
reply
</summary>

<div class="section-content">
<pre>{{parsed.get("reply", "")}}</pre>
</div>

</details>

{% if parsed.get("control") %}

<details class="section">

<summary>
control
</summary>

<div class="section-content">
<pre>{{pretty(parsed.get("control"))}}</pre>
</div>

</details>

{% endif %}

{% if parsed.get("signal") %}

<details class="section">

<summary>
signal (+{{parsed.get("signal", {})|length}})
</summary>

<div class="section-content">

<div class="signal-grid">

{% for k, v in parsed.get("signal", {}).items() %}

<details class="signal-box">

<summary>
{{k}}
</summary>

<pre>{{pretty(v)}}</pre>

</details>

{% endfor %}

</div>

</div>

</details>

{% endif %}

{% else %}

<details class="section" open>

<summary>
raw
</summary>

<div class="section-content">
<pre>{{pretty(log)}}</pre>
</div>

</details>

{% endif %}

</div>

</details>

{% endfor %}

</div>

</div>

<script>

const AUTO_REFRESH_KEY = "logviewer.autoRefresh";
const SCROLL_KEY = "logviewer.scrollY";
const OPEN_LOGS_KEY = "logviewer.openLogs";
const REFRESH_INTERVAL_MS = 5000;

let autoRefreshTimer = null;
let lastRefreshAt = Date.now();
let statusTickTimer = null;

document.querySelectorAll(".event-chip").forEach(chip => {

    chip.addEventListener("click", () => {

        const checkbox =
            chip.querySelector("input");

        checkbox.checked = !checkbox.checked;

        chip.classList.toggle(
            "selected",
            checkbox.checked
        );
    });
});

function saveViewState() {

    sessionStorage.setItem(
        SCROLL_KEY,
        String(window.scrollY)
    );

    const openKeys = [
        ...document.querySelectorAll(
            "details.log[open]"
        )
    ].map(d => d.dataset.logKey);

    sessionStorage.setItem(
        OPEN_LOGS_KEY,
        JSON.stringify(openKeys)
    );
}

function restoreViewState() {

    const y = sessionStorage.getItem(SCROLL_KEY);

    if (y !== null) {
        window.scrollTo(0, parseInt(y, 10));
        sessionStorage.removeItem(SCROLL_KEY);
    }

    const raw = sessionStorage.getItem(OPEN_LOGS_KEY);

    if (raw) {
        try {
            const keys = JSON.parse(raw);
            for (const key of keys) {
                const el = document.querySelector(
                    `details.log[data-log-key="${
                        CSS.escape(key)
                    }"]`
                );
                if (el) el.open = true;
            }
        } catch (e) {
            // ignore corrupt state
        }
        sessionStorage.removeItem(OPEN_LOGS_KEY);
    }
}

async function refreshLogs() {

    saveViewState();

    try {
        await fetch(
            "/refresh",
            { method: "POST" }
        );
    } catch (e) {
        console.error("refresh failed:", e);
    }

    // Reload current URL so query-string filters survive.
    window.location.reload();
}

function updateStatus() {

    const status = document.getElementById("refreshStatus");
    if (!status) return;

    const on = autoRefreshTimer !== null;

    if (!on) {
        status.textContent = "";
        return;
    }

    const secs = Math.round(
        (Date.now() - lastRefreshAt) / 1000
    );

    status.textContent =
        `auto • refreshed ${secs}s ago`;
}

function setAutoRefresh(on) {

    if (autoRefreshTimer) {
        clearInterval(autoRefreshTimer);
        autoRefreshTimer = null;
    }

    if (statusTickTimer) {
        clearInterval(statusTickTimer);
        statusTickTimer = null;
    }

    if (on) {
        autoRefreshTimer = setInterval(
            refreshLogs,
            REFRESH_INTERVAL_MS
        );
        statusTickTimer = setInterval(
            updateStatus,
            1000
        );
    }

    sessionStorage.setItem(
        AUTO_REFRESH_KEY,
        on ? "1" : "0"
    );

    updateStatus();
}

window.addEventListener("DOMContentLoaded", () => {

    restoreViewState();

    const toggle = document.getElementById(
        "autoRefreshToggle"
    );

    const on =
        sessionStorage.getItem(AUTO_REFRESH_KEY) === "1";

    toggle.checked = on;

    setAutoRefresh(on);

    toggle.addEventListener(
        "change",
        (e) => setAutoRefresh(e.target.checked)
    );
});

function selectedLogs() {

    return [
        ...document.querySelectorAll(
            ".export-checkbox:checked"
        )
    ].map(
        x => JSON.parse(x.dataset.log)
    );
}

function download(filename, content, mime) {

    const blob = new Blob(
        [content],
        { type: mime }
    );

    const url =
        URL.createObjectURL(blob);

    const a =
        document.createElement("a");

    a.href = url;
    a.download = filename;

    document.body.appendChild(a);

    a.click();

    a.remove();

    URL.revokeObjectURL(url);
}

function downloadJsonl() {

    const logs = selectedLogs();

    const out = logs
        .map(x => JSON.stringify(x))
        .join("\n");

    download(
        "logs.jsonl",
        out,
        "application/json"
    );
}

function downloadReadable() {

    const logs = selectedLogs();

    let out = [];

    for (const log of logs) {

        let chunk = [];

        chunk.push("=".repeat(80));

        chunk.push(
            `[${log.event}] `
            + `${log.session_id || ""} `
            + `${log.call_id || ""}`
        );

        if (log.ts) {
            chunk.push(`time: ${log.ts}`);
        }

        if (log.model) {
            chunk.push(`model: ${log.model}`);
        }

        if (log.latency_ms) {
            chunk.push(
                `latency: ${log.latency_ms} ms`
            );
        }

        if (
            log.input_tokens
            || log.output_tokens
        ) {

            chunk.push(
                `tokens: in=${log.input_tokens || "-"} `
                + `out=${log.output_tokens || "-"}`
            );
        }

        if (log.raw_output) {

            try {

                const parsed =
                    JSON.parse(log.raw_output);

                if (parsed.thinking) {

                    chunk.push(
                        "\n--- thinking ---"
                    );

                    chunk.push(parsed.thinking);
                }

                if (parsed.reply) {

                    chunk.push(
                        "\n--- reply ---"
                    );

                    chunk.push(parsed.reply);
                }

                if (parsed.control) {

                    chunk.push(
                        "\n--- control ---"
                    );

                    chunk.push(
                        JSON.stringify(
                            parsed.control,
                            null,
                            2
                        )
                    );
                }

                if (parsed.signal) {

                    chunk.push(
                        "\n--- signal ---"
                    );

                    chunk.push(
                        JSON.stringify(
                            parsed.signal,
                            null,
                            2
                        )
                    );
                }

            } catch {

                chunk.push(
                    "\n--- raw_output ---"
                );

                chunk.push(log.raw_output);
            }
        }

        out.push(chunk.join("\n"));
    }

    download(
        "logs_readable.txt",
        out.join("\n\n"),
        "text/plain"
    );
}

</script>

</body>
</html>
"""


def parse_raw(raw):

    if not raw:
        return None

    try:
        return json.loads(raw)
    except Exception:
        return None


def pretty(v):

    if isinstance(v, str):
        return v

    return json.dumps(v, indent=2)


def json_dump(v):
    return json.dumps(v).replace("'", "&#39;")


def human_ts(ts):

    if not ts:
        return ""

    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ts


def load_logs(path):

    logs = []

    with open(path, "r", encoding="utf-8") as f:

        for line in f:

            line = line.strip()

            if not line:
                continue

            try:
                logs.append(json.loads(line))
            except Exception as e:
                print("parse error:", e)

    return logs


def rebuild_indexes():

    global SESSIONS
    global EVENTS

    SESSIONS = sorted({
        x.get("session_id")
        for x in LOGS
        if x.get("session_id")
    })

    EVENTS = sorted({
        x.get("event")
        for x in LOGS
        if x.get("event")
    })


app.jinja_env.globals.update(
    parse_raw=parse_raw,
    pretty=pretty,
    human_ts=human_ts,
    json_dump=json_dump
)


@app.route("/")
def index():

    selected_session = request.args.get("session_id", "")

    selected_events = request.args.getlist("event")

    filtered = LOGS

    if selected_session:

        filtered = [
            x for x in filtered
            if x.get("session_id")
            == selected_session
        ]

    if selected_events:

        filtered = [
            x for x in filtered
            if x.get("event")
            in selected_events
        ]

    filtered = sorted(
        filtered,
        key=lambda x: x.get("ts", "")
    )

    return render_template_string(
        HTML,
        logs=filtered,
        sessions=SESSIONS,
        events=EVENTS,
        selected_session=selected_session,
        selected_events=selected_events,
        total=len(LOGS),
    )


@app.route("/refresh", methods=["POST"])
def refresh():

    global LOGS

    LOGS = load_logs(LOG_PATH)

    rebuild_indexes()

    return {"ok": True, "count": len(LOGS)}


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("jsonl")

    parser.add_argument(
        "--host",
        default="127.0.0.1"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=5000
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable Flask debug mode (Werkzeug reloader + interactive "
             "debugger). DO NOT use in production — the debugger is "
             "RCE-capable. Default: off.",
    )

    args = parser.parse_args()

    global LOGS
    global LOG_PATH

    LOG_PATH = args.jsonl

    LOGS = load_logs(LOG_PATH)

    rebuild_indexes()

    print(f"loaded {len(LOGS)} logs")

    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug
    )


if __name__ == "__main__":
    main()