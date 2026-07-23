#!/usr/bin/env python3
"""Summarize a Cursor session usage JSONL into structured JSON for canvases.

Looks only in <project>/.cursor/usage-logs/. No user-home fallback.

Usage:
  summarize.py <path-to-session.jsonl>
  summarize.py --latest [project-root]
  summarize.py --list [project-root]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_LOG_REL = Path(".cursor") / "usage-logs"

TOKEN_KEYS = (
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
)


def project_log_dir(project: Path) -> Path:
    return project / PROJECT_LOG_REL


def session_jsonl_files(log_dir: Path) -> list[Path]:
    if not log_dir.is_dir():
        return []
    return [
        p
        for p in log_dir.glob("*.jsonl")
        if p.name != "sessions-index.jsonl"
    ]


def find_latest(project: Path | None) -> Path | None:
    if project is None:
        return None
    candidates = session_jsonl_files(project_log_dir(project))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def list_sessions(project: Path | None) -> list[Path]:
    if project is None:
        return []
    return sorted(
        session_jsonl_files(project_log_dir(project)),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def parse_records(path: Path) -> list[dict]:
    records: list[dict] = []
    with path.open() as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def fresh_tokens(input_tokens: int, cache_read: int, cache_write: int) -> int:
    return max(0, input_tokens - cache_read - cache_write)


def empty_token_totals() -> dict[str, int]:
    totals = {key: 0 for key in TOKEN_KEYS}
    totals["fresh_tokens"] = 0
    return totals


def display_totals(totals: dict[str, int]) -> dict[str, str]:
    return {
        "input_tokens": fmt_tokens(totals["input_tokens"]),
        "output_tokens": fmt_tokens(totals["output_tokens"]),
        "cache_read_tokens": fmt_tokens(totals["cache_read_tokens"]),
        "cache_write_tokens": fmt_tokens(totals["cache_write_tokens"]),
        "fresh_tokens": fmt_tokens(totals["fresh_tokens"]),
    }


def model_entry(model: str) -> dict:
    totals = empty_token_totals()
    return {
        "model": model,
        "turn_count": 0,
        "totals": totals,
        "totals_display": display_totals(totals),
        "cache_read_pct": 0.0,
    }


def finalize_model_entry(entry: dict) -> dict:
    totals = entry["totals"]
    input_total = totals["input_tokens"]
    entry["totals_display"] = display_totals(totals)
    entry["cache_read_pct"] = round(
        (totals["cache_read_tokens"] / input_total * 100) if input_total else 0, 1
    )
    return entry


def summarize(path: Path) -> dict:
    records = parse_records(path)
    if not records:
        return {"error": f"No records in {path}"}

    session_id = (
        records[0].get("session_id")
        or records[0].get("conversation_id")
        or path.stem
    )

    events: dict[str, int] = {}
    by_model: dict[str, dict] = {}
    turns: list[dict] = []
    subagents: list[dict] = []
    totals = empty_token_totals()
    statuses: dict[str, int] = {}
    workspace_roots: set[str] = set()
    project = None
    user_email = None
    cursor_version = None
    duration_ms = None
    reason = None
    final_status = None
    precompacts: list[dict] = []

    for record in records:
        event = record.get("hook_event") or record.get("hook_event_name") or "unknown"
        events[event] = events.get(event, 0) + 1

        for root in record.get("workspace_roots") or []:
            workspace_roots.add(str(root))

        if record.get("project"):
            project = record["project"]
        if record.get("user_email"):
            user_email = record["user_email"]
        if record.get("cursor_version"):
            cursor_version = record["cursor_version"]

        if event == "stop":
            model = str(record.get("model") or record.get("model_id") or "unknown")
            input_tokens = int(record.get("input_tokens") or 0)
            output_tokens = int(record.get("output_tokens") or 0)
            cache_read = int(record.get("cache_read_tokens") or 0)
            cache_write = int(record.get("cache_write_tokens") or 0)
            if (
                input_tokens == 0
                and output_tokens == 0
                and cache_read == 0
                and cache_write == 0
            ):
                continue
            fresh = fresh_tokens(input_tokens, cache_read, cache_write)

            totals["input_tokens"] += input_tokens
            totals["output_tokens"] += output_tokens
            totals["cache_read_tokens"] += cache_read
            totals["cache_write_tokens"] += cache_write
            totals["fresh_tokens"] += fresh

            if model not in by_model:
                by_model[model] = model_entry(model)
            entry = by_model[model]
            entry["turn_count"] += 1
            entry["totals"]["input_tokens"] += input_tokens
            entry["totals"]["output_tokens"] += output_tokens
            entry["totals"]["cache_read_tokens"] += cache_read
            entry["totals"]["cache_write_tokens"] += cache_write
            entry["totals"]["fresh_tokens"] += fresh

            status = str(record.get("status") or "unknown")
            statuses[status] = statuses.get(status, 0) + 1

            turns.append(
                {
                    "turn": len(turns) + 1,
                    "logged_at": record.get("logged_at"),
                    "generation_id": record.get("generation_id"),
                    "model": model,
                    "status": status,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cache_read_tokens": cache_read,
                    "cache_write_tokens": cache_write,
                    "fresh_tokens": fresh,
                    "cache_read_pct": round(
                        (cache_read / input_tokens * 100) if input_tokens else 0, 1
                    ),
                }
            )
        elif event in ("subagentStop", "subagentStart"):
            subagents.append(
                {
                    "event": event,
                    "type": record.get("subagent_type"),
                    "status": record.get("status"),
                    "description": record.get("description") or record.get("task"),
                    "duration_ms": record.get("duration_ms"),
                    "message_count": record.get("message_count"),
                    "tool_call_count": record.get("tool_call_count"),
                    "logged_at": record.get("logged_at"),
                }
            )
        elif event == "preCompact":
            precompacts.append(
                {
                    "logged_at": record.get("logged_at"),
                    "context_tokens": record.get("context_tokens"),
                    "context_usage_percent": record.get("context_usage_percent"),
                    "messages_to_compact": record.get("messages_to_compact"),
                    "trigger": record.get("trigger"),
                }
            )
        elif event == "sessionEnd":
            duration_ms = record.get("duration_ms", duration_ms)
            reason = record.get("reason", reason)
            final_status = record.get("final_status", final_status)

    input_total = totals["input_tokens"]
    cache_read_total = totals["cache_read_tokens"]
    fresh_total = totals["fresh_tokens"]
    output_total = totals["output_tokens"]

    models_list = [
        finalize_model_entry(entry)
        for entry in sorted(
            by_model.values(),
            key=lambda item: item["totals"]["input_tokens"],
            reverse=True,
        )
    ]
    for entry in models_list:
        m_input = entry["totals"]["input_tokens"]
        entry["prompt_share_pct"] = round(
            (m_input / input_total * 100) if input_total else 0, 1
        )
        entry["output_share_pct"] = round(
            (entry["totals"]["output_tokens"] / output_total * 100)
            if output_total
            else 0,
            1,
        )
        entry["turn_share_pct"] = round(
            (entry["turn_count"] / len(turns) * 100) if turns else 0, 1
        )
    # turn counts only (for chips / simple maps)
    models = {entry["model"]: entry["turn_count"] for entry in models_list}

    return {
        "session_id": session_id,
        "log_path": str(path),
        "project": project,
        "workspace_roots": sorted(workspace_roots),
        "user_email": user_email,
        "cursor_version": cursor_version,
        "first_event": records[0].get("logged_at"),
        "last_event": records[-1].get("logged_at"),
        "duration_ms": duration_ms,
        "reason": reason,
        "final_status": final_status,
        "event_counts": events,
        "models": models,
        "by_model": models_list,
        "turn_statuses": statuses,
        "turn_count": len(turns),
        "totals": totals,
        "totals_display": display_totals(totals),
        "cache_read_pct": round(
            (cache_read_total / input_total * 100) if input_total else 0, 1
        ),
        "token_mix": {
            "fresh_tokens": fresh_total,
            "cache_read_tokens": cache_read_total,
            "cache_write_tokens": totals["cache_write_tokens"],
            "output_tokens": output_total,
        },
        "turns": turns,
        "subagents": subagents,
        "precompacts": precompacts,
        "has_token_data": any(totals[k] for k in TOKEN_KEYS),
        "notes": [
            "Models are counted only from stop events (turns that used tokens).",
            "Labels match model pricing: Input, Cache write, Cache read, Output.",
            "Input is the uncached part of the prompt (charged at the Input rate).",
            "Prompt total is Cursor's input_tokens: Input + Cache write + Cache read.",
            "fresh_tokens in JSON is the Input line (internal field name).",
            "by_model has per-model turn counts and token totals for this session.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize Cursor session usage logs")
    parser.add_argument("path", nargs="?", help="Path to session JSONL")
    parser.add_argument("--latest", action="store_true", help="Summarize latest session")
    parser.add_argument("--list", action="store_true", help="List known session logs")
    parser.add_argument(
        "--project",
        default=None,
        help="Project root (default: cwd)",
    )
    args = parser.parse_args()

    project = Path(args.project).resolve() if args.project else Path.cwd().resolve()

    if args.list:
        sessions = list_sessions(project)
        print(json.dumps([str(p) for p in sessions], indent=2))
        return 0

    path: Path | None
    if args.path:
        path = Path(args.path).expanduser().resolve()
    elif args.latest:
        path = find_latest(project)
    else:
        path = find_latest(project)

    if path is None or not path.exists():
        print(json.dumps({"error": "No session log found", "project": str(project)}))
        return 1

    print(json.dumps(summarize(path), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
