#!/usr/bin/env python3
"""Log Cursor agent hook payloads for session usage tracking.

Writes only to <workspace>/.cursor/usage-logs/<session_id>.jsonl.
If the hook payload has no workspace root, skip logging.

On stop/sessionEnd, regenerates the project HTML report (script-only).
Always prints {} and exits 0 so it never blocks the agent.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_LOG_REL = Path(".cursor") / "usage-logs"
PROJECT_GITIGNORE = "*\n!.gitignore\n"
PROJECT_REPORT_SCRIPT = SCRIPT_DIR / "project-report.py"

TOKEN_KEYS = (
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
    "cacheReadTokens",
    "cacheWriteTokens",
    "inputTokens",
    "outputTokens",
    "total_tokens",
    "totalTokens",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def session_id_from(payload: dict) -> str:
    for key in ("session_id", "conversation_id", "generation_id"):
        value = payload.get(key)
        if value:
            return str(value)
    return "unknown"


def event_name(payload: dict) -> str:
    for key in ("hook_event_name", "hookEventName"):
        value = payload.get(key)
        if value:
            return str(value)

    if "reason" in payload and "duration_ms" in payload and "final_status" in payload:
        return "sessionEnd"
    if "subagent_type" in payload and "tool_call_count" in payload:
        return "subagentStop"
    if "subagent_type" in payload and "task" in payload and "status" not in payload:
        return "subagentStart"
    if "context_tokens" in payload and "messages_to_compact" in payload:
        return "preCompact"
    if "status" in payload and "loop_count" in payload:
        return "stop"
    if "composer_mode" in payload or (
        "is_background_agent" in payload and "reason" not in payload
    ):
        return "sessionStart"
    return "unknown"


def is_session_end(event: str, payload: dict) -> bool:
    return event == "sessionEnd" or (
        "reason" in payload and "duration_ms" in payload and "final_status" in payload
    )


def workspace_root_from(payload: dict) -> Path | None:
    roots = payload.get("workspace_roots") or []
    if not roots:
        return None
    root = Path(str(roots[0])).expanduser()
    try:
        root = root.resolve()
    except OSError:
        return None
    if root.is_dir():
        return root
    return None


def ensure_project_gitignore(log_dir: Path) -> None:
    gitignore = log_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(PROJECT_GITIGNORE)


def prepare_log_dir(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    ensure_project_gitignore(log_dir)


def sum_token_fields(records: list[dict]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for record in records:
        for key in TOKEN_KEYS:
            value = record.get(key)
            if isinstance(value, (int, float)):
                totals[key] = totals.get(key, 0) + int(value)

        usage = record.get("tokenUsage") or record.get("token_usage")
        if isinstance(usage, dict):
            for key, value in usage.items():
                if isinstance(value, (int, float)):
                    totals[f"tokenUsage.{key}"] = totals.get(f"tokenUsage.{key}", 0) + int(
                        value
                    )
    return totals


def write_report(session_id: str, log_path: Path) -> Path | None:
    records: list[dict] = []
    with log_path.open() as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not records:
        return None

    events: dict[str, int] = {}
    subagents: dict[str, int] = {}
    models: set[str] = set()
    statuses: list[str] = []
    duration_ms = None
    reason = None
    final_status = None
    workspace_roots: set[str] = set()
    precompacts = 0

    for record in records:
        event = record.get("hook_event") or event_name(record)
        events[event] = events.get(event, 0) + 1

        model = record.get("model")
        if model:
            models.add(str(model))

        for root in record.get("workspace_roots") or []:
            workspace_roots.add(str(root))

        if event == "subagentStop":
            kind = record.get("subagent_type") or "unknown"
            subagents[kind] = subagents.get(kind, 0) + 1
        elif event == "subagentStart":
            kind = record.get("subagent_type") or "unknown"
            key = f"{kind} (started)"
            subagents[key] = subagents.get(key, 0) + 1
        elif event == "stop":
            status = record.get("status")
            if status:
                statuses.append(str(status))
        elif event == "preCompact":
            precompacts += 1
        elif event == "sessionEnd":
            duration_ms = record.get("duration_ms", duration_ms)
            reason = record.get("reason", reason)
            final_status = record.get("final_status", final_status)

    token_totals = sum_token_fields(records)
    started = records[0].get("logged_at")
    ended = records[-1].get("logged_at")
    log_dir = log_path.parent

    lines = [
        f"Session usage report: {session_id}",
        f"Generated at: {utc_now()}",
        f"First event: {started}",
        f"Last event: {ended}",
        f"Log dir: {log_dir}",
        "",
        "Session",
        f"  reason: {reason}",
        f"  final_status: {final_status}",
        f"  duration_ms: {duration_ms}",
        f"  models: {', '.join(sorted(models)) or '(none observed)'}",
        f"  workspaces: {', '.join(sorted(workspace_roots)) or '(none observed)'}",
        "",
        "Events",
    ]
    for name, count in sorted(events.items()):
        lines.append(f"  {name}: {count}")

    lines.append("")
    lines.append("Agent turns (stop)")
    if statuses:
        status_counts: dict[str, int] = {}
        for status in statuses:
            status_counts[status] = status_counts.get(status, 0) + 1
        for status, count in sorted(status_counts.items()):
            lines.append(f"  {status}: {count}")
        lines.append(f"  total: {len(statuses)}")
    else:
        lines.append("  (none)")

    lines.append("")
    lines.append("Subagents")
    if subagents:
        for kind, count in sorted(subagents.items()):
            lines.append(f"  {kind}: {count}")
    else:
        lines.append("  (none)")

    lines.append("")
    lines.append(f"Compactions: {precompacts}")
    lines.append("")
    lines.append("Token fields (summed from hook payloads, if present)")
    if token_totals:
        for key, value in sorted(token_totals.items()):
            lines.append(f"  {key}: {value}")
    else:
        lines.append(
            "  (none present — Cursor may not expose tokens on these hooks yet)"
        )
        lines.append("  Full payloads are in the JSONL for inspection.")

    lines.append("")
    lines.append(f"Raw log: {log_path}")

    report_path = log_path.with_name(f"{session_id}-report.txt")
    report_path.write_text("\n".join(lines) + "\n")
    return report_path


def refresh_project_report(project: Path) -> None:
    """Regenerate all-time HTML report. Script-only, no LLM tokens."""
    script = PROJECT_REPORT_SCRIPT
    if not script.exists():
        return
    subprocess.run(
        [sys.executable, str(script), str(project)],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> int:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            print("{}")
            return 0

        payload = json.loads(raw)
        if not isinstance(payload, dict):
            print("{}")
            return 0

        root = workspace_root_from(payload)
        if root is None:
            print("{}")
            return 0

        event = event_name(payload)
        session_id = session_id_from(payload)
        log_dir = root / PROJECT_LOG_REL
        prepare_log_dir(log_dir)
        project = str(root)

        entry = {
            "logged_at": utc_now(),
            "hook_event": event,
            "log_dir": str(log_dir),
            "project": project,
            **payload,
        }

        log_path = log_dir / f"{session_id}.jsonl"
        with log_path.open("a") as handle:
            handle.write(json.dumps(entry, separators=(",", ":"), default=str) + "\n")

        if is_session_end(event, payload):
            write_report(session_id, log_path)

        if event in ("stop", "sessionEnd") or is_session_end(event, payload):
            refresh_project_report(root)

    except Exception:
        pass

    print("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
