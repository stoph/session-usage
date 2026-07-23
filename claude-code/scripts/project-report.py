#!/usr/bin/env python3
"""Build an all-time project usage HTML report from local session logs.

Zero LLM tokens. Safe to run from hooks.

Writes:
  <project>/.claude/usage-logs/report.html
  <project>/.claude/usage-logs/report-data.json

Usage:
  project-report.py [project-root]
  project-report.py --open [project-root]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_LOG_REL = Path(".claude") / "usage-logs"


def load_summarize():
    path = SCRIPT_DIR / "summarize.py"
    spec = importlib.util.spec_from_file_location("session_usage_summarize", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def session_files(log_dir: Path) -> list[Path]:
    return sorted(
        (
            p
            for p in log_dir.glob("*.jsonl")
            if p.name != "sessions-index.jsonl" and not p.name.endswith(".state.jsonl")
        ),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def build_project_summary(project: Path) -> dict:
    summarize = load_summarize()
    log_dir = project / PROJECT_LOG_REL
    sessions: list[dict] = []

    if log_dir.is_dir():
        for path in session_files(log_dir):
            data = summarize.summarize(path)
            if "error" in data:
                continue
            sessions.append(data)

    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "fresh_tokens": 0,
    }
    by_model: dict[str, dict] = {}
    turn_count = 0
    event_counts: dict[str, int] = {}
    subagent_count = 0

    for session in sessions:
        for key in totals:
            totals[key] += int(session.get("totals", {}).get(key, 0))
        turn_count += int(session.get("turn_count", 0))
        subagent_count += len(session.get("subagents") or [])
        for event, count in (session.get("event_counts") or {}).items():
            event_counts[event] = event_counts.get(event, 0) + count

        for entry in session.get("by_model") or []:
            model = entry.get("model") or "unknown"
            if model not in by_model:
                by_model[model] = {
                    "model": model,
                    "turn_count": 0,
                    "session_count": 0,
                    "totals": {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "cache_read_tokens": 0,
                        "cache_write_tokens": 0,
                        "fresh_tokens": 0,
                    },
                }
            bucket = by_model[model]
            bucket["turn_count"] += int(entry.get("turn_count", 0))
            bucket["session_count"] += 1
            for key in bucket["totals"]:
                bucket["totals"][key] += int(entry.get("totals", {}).get(key, 0))

    input_total = totals["input_tokens"]
    output_total = totals["output_tokens"]
    cache_read_total = totals["cache_read_tokens"]

    models_list = []
    for entry in by_model.values():
        m_totals = entry["totals"]
        m_input = m_totals["input_tokens"]
        models_list.append(
            {
                "model": entry["model"],
                "turn_count": entry["turn_count"],
                "session_count": entry["session_count"],
                "totals": m_totals,
                "totals_display": {
                    "input_tokens": summarize.fmt_tokens(m_totals["input_tokens"]),
                    "output_tokens": summarize.fmt_tokens(m_totals["output_tokens"]),
                    "cache_read_tokens": summarize.fmt_tokens(m_totals["cache_read_tokens"]),
                    "cache_write_tokens": summarize.fmt_tokens(m_totals["cache_write_tokens"]),
                    "fresh_tokens": summarize.fmt_tokens(m_totals["fresh_tokens"]),
                },
                "cache_read_pct": round(
                    (m_totals["cache_read_tokens"] / m_input * 100) if m_input else 0, 1
                ),
                "prompt_share_pct": round(
                    (m_input / input_total * 100) if input_total else 0, 1
                ),
                "output_share_pct": round(
                    (m_totals["output_tokens"] / output_total * 100)
                    if output_total
                    else 0,
                    1,
                ),
                "turn_share_pct": round(
                    (entry["turn_count"] / turn_count * 100) if turn_count else 0, 1
                ),
            }
        )

    models_list.sort(key=lambda item: item["totals"]["input_tokens"], reverse=True)
    models = {entry["model"]: entry["turn_count"] for entry in models_list}

    return {
        "generated_at": utc_now(),
        "project": str(project),
        "project_name": project.name,
        "log_dir": str(log_dir),
        "session_count": len(sessions),
        "turn_count": turn_count,
        "subagent_count": subagent_count,
        "totals": totals,
        "totals_display": {
            "input_tokens": summarize.fmt_tokens(totals["input_tokens"]),
            "output_tokens": summarize.fmt_tokens(totals["output_tokens"]),
            "cache_read_tokens": summarize.fmt_tokens(totals["cache_read_tokens"]),
            "cache_write_tokens": summarize.fmt_tokens(totals["cache_write_tokens"]),
            "fresh_tokens": summarize.fmt_tokens(totals["fresh_tokens"]),
        },
        "cache_read_pct": round(
            (cache_read_total / input_total * 100) if input_total else 0, 1
        ),
        "models": models,
        "by_model": models_list,
        "event_counts": event_counts,
        "sessions": sessions,
        "notes": [
            "Project totals: every session in this project's usage-logs folder, all turns summed.",
            "Models are counted only from stop events (turns that used tokens).",
            "Labels match model pricing: Input, Cache write, Cache read, Output.",
            "Input is the uncached part of the prompt. Prompt total is Input + Cache write + Cache read.",
            "by_model prompt_share_pct is share of project prompt total.",
            "Regenerated by script (no LLM tokens). Auto-updated on agent stop/sessionEnd.",
        ],
    }


def render_html(data: dict) -> str:
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Usage — {data.get("project_name", "project")}</title>
<style>
  :root {{
    color-scheme: light dark;
    --bg: #f4f2ed;
    --surface: #fffdf8;
    --text: #1c1915;
    --muted: #6b645a;
    --line: #ddd6cb;
    --accent: #0f6b5c;
    --fresh: #b45309;
    --cache: #0f6b5c;
    --write: #1d4ed8;
    --output: #7c3aed;
    --input: #0e7490;
    --chip: #ebe6dc;
    --row: #faf8f4;
    --mono: "IBM Plex Mono", "SF Mono", ui-monospace, monospace;
    --sans: "IBM Plex Sans", "Segoe UI", sans-serif;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #12110f;
      --surface: #1b1916;
      --text: #f3efe7;
      --muted: #a39b8f;
      --line: #2f2b26;
      --accent: #3dbaa4;
      --fresh: #f59e0b;
      --cache: #34d399;
      --write: #60a5fa;
      --output: #c4b5fd;
      --input: #22d3ee;
      --chip: #26221d;
      --row: #221f1b;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: var(--sans);
    background: var(--bg);
    color: var(--text);
    line-height: 1.45;
  }}
  main {{
    max-width: 1120px;
    margin: 0 auto;
    padding: 28px 20px 64px;
  }}
  h1 {{ margin: 0 0 4px; font-size: 1.75rem; letter-spacing: -0.02em; }}
  h2 {{ margin: 28px 0 12px; font-size: 1.1rem; }}
  h3 {{ margin: 0 0 10px; font-size: 0.95rem; }}
  .meta, .note, .muted, .help {{ color: var(--muted); }}
  .meta {{ font-size: 0.9rem; margin-bottom: 12px; }}
  .help {{
    font-size: 0.88rem;
    margin: 0 0 16px;
    max-width: 70ch;
  }}
  .stats {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 10px;
  }}
  .stat {{
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 14px 14px 12px;
  }}
  .stat .value {{
    font-size: 1.35rem;
    font-weight: 650;
    font-variant-numeric: tabular-nums;
  }}
  .stat .label {{ color: var(--muted); font-size: 0.8rem; margin-top: 2px; }}
  .panel {{
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 14px;
    margin-top: 12px;
  }}
  .mix-row {{
    display: grid;
    grid-template-columns: 120px 1fr 72px 56px;
    gap: 10px;
    align-items: center;
    margin: 8px 0;
    font-size: 0.9rem;
  }}
  .mix-row .track {{
    height: 12px;
    background: var(--chip);
    border-radius: 999px;
    overflow: hidden;
  }}
  .mix-row .fill {{
    display: block;
    height: 100%;
    border-radius: 999px;
    min-width: 0;
  }}
  .mix-row .val, .mix-row .pct {{
    font-variant-numeric: tabular-nums;
    text-align: right;
    color: var(--muted);
    font-size: 0.85rem;
  }}
  .mix-row.total {{
    margin-top: 12px;
    padding-top: 10px;
    border-top: 1px solid var(--line);
    font-weight: 600;
  }}
  .mix-row.total .track {{ display: none; }}
  .mix-row.output {{
    margin-top: 8px;
    padding-top: 10px;
    border-top: 1px dashed var(--line);
  }}
  .toolbar {{
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    align-items: center;
    margin: 8px 0 14px;
  }}
  input[type="search"] {{
    flex: 1;
    min-width: 220px;
    border: 1px solid var(--line);
    background: var(--surface);
    color: var(--text);
    border-radius: 8px;
    padding: 10px 12px;
    font: inherit;
  }}
  button {{
    border: 1px solid var(--line);
    background: var(--surface);
    color: var(--text);
    border-radius: 8px;
    padding: 9px 12px;
    font: inherit;
    cursor: pointer;
  }}
  button:hover {{ border-color: var(--accent); }}
  .session {{
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 10px;
    margin-bottom: 10px;
    overflow: hidden;
  }}
  .session summary {{
    list-style: none;
    cursor: pointer;
    padding: 12px 14px;
    display: grid;
    grid-template-columns: 1.4fr 0.7fr 0.7fr 0.7fr 0.7fr 0.6fr;
    gap: 8px;
    align-items: center;
  }}
  .session summary::-webkit-details-marker {{ display: none; }}
  .session summary:hover {{ background: var(--row); }}
  .session[open] summary {{ border-bottom: 1px solid var(--line); }}
  .id {{ font-family: var(--mono); font-size: 0.85rem; }}
  .num {{ font-variant-numeric: tabular-nums; text-align: right; }}
  .chips {{ display: flex; gap: 6px; flex-wrap: wrap; }}
  .chip {{
    background: var(--chip);
    border-radius: 999px;
    padding: 2px 8px;
    font-size: 0.75rem;
    color: var(--muted);
  }}
  .detail {{ padding: 14px; }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
  }}
  th, td {{
    padding: 8px 6px;
    border-bottom: 1px solid var(--line);
    text-align: left;
  }}
  th {{ color: var(--muted); font-weight: 550; }}
  td.num, th.num {{ text-align: right; }}
  .empty {{
    border: 1px dashed var(--line);
    border-radius: 10px;
    padding: 24px;
    color: var(--muted);
  }}
  .head-row {{
    display: grid;
    grid-template-columns: 1.4fr 0.7fr 0.7fr 0.7fr 0.7fr 0.6fr;
    gap: 8px;
    padding: 0 14px 8px;
    color: var(--muted);
    font-size: 0.78rem;
  }}
  @media (max-width: 800px) {{
    .session summary, .head-row {{ grid-template-columns: 1fr 1fr; }}
    .head-row {{ display: none; }}
    .mix-row {{ grid-template-columns: 90px 1fr 56px 48px; }}
  }}
</style>
</head>
<body>
<main>
  <h1 id="title">Project usage</h1>
  <p class="meta" id="meta"></p>
  <p class="help">
    Totals for <strong>all sessions and turns</strong> in this project.
    Labels match how models are charged:
    <strong>Input</strong> is the part of the prompt that was not already cached
    (full Input rate).
    <strong>Cache write</strong> is prompt content stored into the cache.
    <strong>Cache read</strong> is prompt content reused from the cache.
    <strong>Prompt total</strong> is all of those together (Input + Cache write + Cache read).
    <strong>Output</strong> is what the model generated.
  </p>

  <section>
    <h2>Project summary</h2>
    <div class="stats" id="stats"></div>
    <div class="panel">
      <h3>Prompt breakdown (all sessions)</h3>
      <div id="project-mix"></div>
    </div>
    <div class="panel" style="margin-top:12px">
      <h3>Models (all sessions)</h3>
      <p class="muted" style="font-size:0.85rem;margin:0 0 10px">
        Only models that ran at least one turn. Share % is of project prompt total.
      </p>
      <div id="project-models"></div>
    </div>
  </section>

  <section>
    <h2>Sessions</h2>
    <div class="toolbar">
      <input id="filter" type="search" placeholder="Filter by session id, model…" />
      <button type="button" id="expand-all">Expand all</button>
      <button type="button" id="collapse-all">Collapse all</button>
    </div>
    <div class="head-row">
      <div>Session</div>
      <div class="num">Turns</div>
      <div class="num">Prompt</div>
      <div class="num">Input</div>
      <div class="num">Cache read</div>
      <div class="num">Output</div>
    </div>
    <div id="sessions"></div>
  </section>

  <p class="note" id="notes"></p>
</main>
<script id="data" type="application/json">{payload}</script>
<script>
const data = JSON.parse(document.getElementById("data").textContent);

function fmt(n) {{
  if (n == null) return "—";
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return String(n);
}}

function fmtTime(iso) {{
  if (!iso) return "—";
  try {{
    return new Date(iso).toLocaleString(undefined, {{
      month: "short", day: "numeric", hour: "numeric", minute: "2-digit"
    }});
  }} catch {{
    return iso;
  }}
}}

function pctOf(part, whole) {{
  if (!whole) return 0;
  return (part / whole) * 100;
}}

/** One row per pricing category; bar width = share of prompt total. */
function mixRowsHtml(totals, display) {{
  const prompt = totals.input_tokens || 0;
  const rows = [
    ["Input", totals.fresh_tokens || 0, display?.fresh_tokens || fmt(totals.fresh_tokens || 0), "var(--fresh)"],
    ["Cache write", totals.cache_write_tokens || 0, display?.cache_write_tokens || fmt(totals.cache_write_tokens || 0), "var(--write)"],
    ["Cache read", totals.cache_read_tokens || 0, display?.cache_read_tokens || fmt(totals.cache_read_tokens || 0), "var(--cache)"],
  ];
  const promptDisplay = display?.input_tokens || fmt(prompt);
  const outputDisplay = display?.output_tokens || fmt(totals.output_tokens || 0);

  return rows.map(([label, value, shown, color]) => {{
    const pct = pctOf(value, prompt);
    const width = Math.max(pct > 0 ? 1.5 : 0, pct);
    return `<div class="mix-row">
      <div>${{label}}</div>
      <div class="track"><span class="fill" style="width:${{width}}%;background:${{color}}"></span></div>
      <div class="val">${{shown}}</div>
      <div class="pct">${{pct.toFixed(1)}}%</div>
    </div>`;
  }}).join("") + `
    <div class="mix-row total">
      <div>Prompt total</div>
      <div></div>
      <div class="val">${{promptDisplay}}</div>
      <div class="pct">100%</div>
    </div>
    <div class="mix-row output">
      <div>Output</div>
      <div class="track"><span class="fill" style="width:${{Math.min(100, pctOf(totals.output_tokens || 0, prompt) || 0)}}%;background:var(--output)"></span></div>
      <div class="val">${{outputDisplay}}</div>
      <div class="pct"></div>
    </div>`;
}}

document.getElementById("title").textContent = "Usage — " + (data.project_name || "project");
document.getElementById("meta").textContent =
  data.project + " · generated " + fmtTime(data.generated_at) +
  " · " + data.session_count + " session" + (data.session_count === 1 ? "" : "s") +
  " · " + data.turn_count + " turns";

const stats = [
  ["Sessions", data.session_count],
  ["Turns", data.turn_count],
  ["Prompt total", data.totals_display.input_tokens],
  ["Input", data.totals_display.fresh_tokens],
  ["Cache read", data.totals_display.cache_read_tokens],
  ["Cache % of prompt", (data.cache_read_pct ?? 0).toFixed(1) + "%"],
  ["Output", data.totals_display.output_tokens],
];
document.getElementById("stats").innerHTML = stats.map(([label, value]) =>
  `<div class="stat"><div class="value">${{value}}</div><div class="label">${{label}}</div></div>`
).join("");

document.getElementById("project-mix").innerHTML = mixRowsHtml(data.totals || {{}}, data.totals_display);

function modelTableHtml(entries, {{ showSessions = false }} = {{}}) {{
  if (!entries || !entries.length) {{
    return `<p class="muted">No models with token-bearing turns.</p>`;
  }}
  const sessionCol = showSessions ? "<th class='num'>Sessions</th>" : "";
  return `<table>
    <thead><tr>
      <th>Model</th>
      ${{sessionCol}}
      <th class="num">Turns</th>
      <th class="num">Prompt share</th>
      <th class="num">Prompt</th>
      <th class="num">Input</th>
      <th class="num">Cache write</th>
      <th class="num">Cache read</th>
      <th class="num">Output</th>
      <th class="num">Output share</th>
    </tr></thead>
    <tbody>
      ${{entries.map(m => {{
        const sessions = showSessions
          ? `<td class="num">${{m.session_count ?? "—"}}</td>`
          : "";
        return `<tr>
          <td>${{m.model}}</td>
          ${{sessions}}
          <td class="num">${{m.turn_count}}</td>
          <td class="num">${{(m.prompt_share_pct ?? 0).toFixed(1)}}%</td>
          <td class="num">${{m.totals_display?.input_tokens || fmt(m.totals?.input_tokens)}}</td>
          <td class="num">${{m.totals_display?.fresh_tokens || fmt(m.totals?.fresh_tokens)}}</td>
          <td class="num">${{m.totals_display?.cache_write_tokens || fmt(m.totals?.cache_write_tokens)}}</td>
          <td class="num">${{m.totals_display?.cache_read_tokens || fmt(m.totals?.cache_read_tokens)}}</td>
          <td class="num">${{m.totals_display?.output_tokens || fmt(m.totals?.output_tokens)}}</td>
          <td class="num">${{(m.output_share_pct ?? 0).toFixed(1)}}%</td>
        </tr>`;
      }}).join("")}}
    </tbody>
  </table>`;
}}

document.getElementById("project-models").innerHTML = modelTableHtml(data.by_model || [], {{ showSessions: true }});

function modelBreakdownHtml(entries) {{
  if (!entries || !entries.length) return "";
  if (entries.length === 1) {{
    return `<p class="muted" style="font-size:0.85rem;margin:12px 0 0">
      Single model: ${{entries[0].model}} (${{entries[0].turn_count}} turns)
    </p>`;
  }}
  return `<div style="margin-top:14px">
    <h3>Per model</h3>
    ${{modelTableHtml(entries)}}
    ${{entries.map(m => `
      <div class="panel" style="margin-top:10px">
        <h3>${{m.model}} · ${{m.turn_count}} turns · ${{(m.prompt_share_pct ?? 0).toFixed(1)}}% of session prompt</h3>
        ${{mixRowsHtml(m.totals || {{}}, m.totals_display)}}
      </div>
    `).join("")}}
  </div>`;
}}

function turnRows(turns) {{
  if (!turns || !turns.length) return "<p class='muted'>No token-bearing turns logged.</p>";
  return `<table>
    <thead><tr>
      <th>Turn</th><th>Status</th><th>Model</th>
      <th class="num">Prompt</th><th class="num">Input</th>
      <th class="num">Cache read</th><th class="num">Cache %</th><th class="num">Output</th>
    </tr></thead>
    <tbody>
      ${{turns.map(t => `<tr>
        <td>${{t.turn}}</td>
        <td>${{t.status || "—"}}</td>
        <td>${{t.model || "—"}}</td>
        <td class="num">${{fmt(t.input_tokens)}}</td>
        <td class="num">${{fmt(t.fresh_tokens)}}</td>
        <td class="num">${{fmt(t.cache_read_tokens)}}</td>
        <td class="num">${{(t.cache_read_pct ?? 0).toFixed(1)}}%</td>
        <td class="num">${{fmt(t.output_tokens)}}</td>
      </tr>`).join("")}}
    </tbody>
  </table>`;
}}

function subagentRows(items) {{
  if (!items || !items.length) return "";
  return `<h3 style="margin:16px 0 8px">Subagents</h3>
  <table>
    <thead><tr>
      <th>Event</th><th>Type</th><th>Status</th><th>Description</th>
      <th class="num">Msgs</th><th class="num">Tools</th><th class="num">Duration</th>
    </tr></thead>
    <tbody>
      ${{items.map(s => `<tr>
        <td>${{s.event || "—"}}</td>
        <td>${{s.type || "—"}}</td>
        <td>${{s.status || "—"}}</td>
        <td>${{s.description || "—"}}</td>
        <td class="num">${{s.message_count ?? "—"}}</td>
        <td class="num">${{s.tool_call_count ?? "—"}}</td>
        <td class="num">${{s.duration_ms != null ? (s.duration_ms / 1000).toFixed(1) + "s" : "—"}}</td>
      </tr>`).join("")}}
    </tbody>
  </table>`;
}}

function renderSessions(filter = "") {{
  const q = filter.trim().toLowerCase();
  const root = document.getElementById("sessions");
  const sessions = (data.sessions || []).filter(s => {{
    if (!q) return true;
    const blob = [
      s.session_id,
      ...(Object.keys(s.models || {{}})),
      s.first_event,
      s.last_event,
    ].join(" ").toLowerCase();
    return blob.includes(q);
  }});

  if (!sessions.length) {{
    root.innerHTML = `<div class="empty">No sessions match.</div>`;
    return;
  }}

  root.innerHTML = sessions.map(s => {{
    const id = s.session_id || "unknown";
    const short = id.slice(0, 8);
    const modelChips = Object.keys(s.models || {{}}).map(m =>
      `<span class="chip">${{m}} ×${{s.models[m]}}</span>`
    ).join("");
    return `<details class="session" data-id="${{id}}">
      <summary>
        <div>
          <div class="id">${{short}}</div>
          <div class="muted" style="font-size:0.8rem">${{fmtTime(s.first_event)}} – ${{fmtTime(s.last_event)}}</div>
          <div class="chips" style="margin-top:4px">${{modelChips}}</div>
        </div>
        <div class="num">${{s.turn_count}}</div>
        <div class="num">${{s.totals_display?.input_tokens || "0"}}</div>
        <div class="num">${{s.totals_display?.fresh_tokens || "0"}}</div>
        <div class="num">${{s.totals_display?.cache_read_tokens || "0"}}</div>
        <div class="num">${{s.totals_display?.output_tokens || "0"}}</div>
      </summary>
      <div class="detail">
        <div class="panel" style="margin:0 0 14px">
          <h3>Session total (${{s.turn_count}} turns)</h3>
          ${{mixRowsHtml(s.totals || {{}}, s.totals_display)}}
          ${{modelBreakdownHtml(s.by_model || [])}}
        </div>
        <p class="muted" style="font-size:0.85rem;margin:0 0 10px">
          ${{id}} · cache ${{(s.cache_read_pct ?? 0).toFixed(1)}}% of prompt ·
          ${{s.final_status ? ("status " + s.final_status) : "in progress or incomplete"}}
        </p>
        ${{turnRows(s.turns)}}
        ${{subagentRows(s.subagents)}}
      </div>
    </details>`;
  }}).join("");
}}

renderSessions();
document.getElementById("filter").addEventListener("input", (e) => renderSessions(e.target.value));
document.getElementById("expand-all").addEventListener("click", () => {{
  document.querySelectorAll(".session").forEach(el => el.open = true);
}});
document.getElementById("collapse-all").addEventListener("click", () => {{
  document.querySelectorAll(".session").forEach(el => el.open = false);
}});

document.getElementById("notes").innerHTML = (data.notes || []).join(" ");
</script>
</body>
</html>
"""


def write_report(project: Path) -> tuple[Path, Path]:
    data = build_project_summary(project)
    log_dir = project / PROJECT_LOG_REL
    log_dir.mkdir(parents=True, exist_ok=True)

    gitignore = log_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n!.gitignore\n")

    json_path = log_dir / "report-data.json"
    html_path = log_dir / "report.html"
    json_path.write_text(json.dumps(data, indent=2) + "\n")
    html_path.write_text(render_html(data))
    return html_path, json_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build project usage HTML report")
    parser.add_argument(
        "project",
        nargs="?",
        default=None,
        help="Project root (default: cwd)",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open report.html after writing",
    )
    args = parser.parse_args()
    project = Path(args.project).expanduser().resolve() if args.project else Path.cwd().resolve()

    html_path, json_path = write_report(project)
    print(json.dumps({"html": str(html_path), "data": str(json_path)}, indent=2))

    if args.open:
        subprocess.run(["open", str(html_path)], check=False)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
