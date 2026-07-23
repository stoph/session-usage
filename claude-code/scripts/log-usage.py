#!/usr/bin/env python3
"""Log Claude Code hook payloads for per-project usage tracking.

Writes only to <project>/.claude/usage-logs/<session_id>.jsonl.
Project root comes from CLAUDE_PROJECT_DIR, else hook cwd.
No project root → do not log.

Token counts are not on most hook payloads. On Stop / SubagentStop,
usage is derived from the transcript JSONL (assistant message.usage).
Normalized fields match the HTML reporter:
  input_tokens = prompt total (fresh + cache write + cache read)
  cache_write_tokens = cache_creation_input_tokens
  cache_read_tokens = cache_read_input_tokens
  output_tokens = output_tokens

Always exits 0. Prints nothing on success so Stop hooks never block.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_LOG_REL = Path(".claude") / "usage-logs"
PROJECT_GITIGNORE = "*\n!.gitignore\n"
PROJECT_REPORT_SCRIPT = SCRIPT_DIR / "project-report.py"

EMPTY_USAGE = {
    "input_tokens": 0,
    "output_tokens": 0,
    "cache_read_tokens": 0,
    "cache_write_tokens": 0,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def project_root_from(payload: dict) -> Path | None:
    for candidate in (
        os.environ.get("CLAUDE_PROJECT_DIR"),
        payload.get("cwd"),
    ):
        if not candidate:
            continue
        root = Path(str(candidate)).expanduser()
        try:
            root = root.resolve()
        except OSError:
            continue
        if root.is_dir():
            return root
    return None


def session_id_from(payload: dict) -> str:
    for key in ("session_id", "sessionId"):
        value = payload.get(key)
        if value:
            return str(value)
    return "unknown"


def event_name(payload: dict) -> str:
    raw = payload.get("hook_event_name") or payload.get("hookEventName") or "unknown"
    return str(raw)


def normalize_event(event: str) -> str:
    """Map Claude event names to stable lowercase keys used by the reporter."""
    mapping = {
        "SessionStart": "sessionStart",
        "SessionEnd": "sessionEnd",
        "Stop": "stop",
        "SubagentStart": "subagentStart",
        "SubagentStop": "subagentStop",
        "PreCompact": "preCompact",
    }
    return mapping.get(event, event[:1].lower() + event[1:] if event else "unknown")


def ensure_project_gitignore(log_dir: Path) -> None:
    gitignore = log_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(PROJECT_GITIGNORE)


def prepare_log_dir(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    ensure_project_gitignore(log_dir)


def normalize_claude_usage(usage: dict) -> dict[str, int]:
    fresh = int(usage.get("input_tokens") or 0)
    cache_write = int(usage.get("cache_creation_input_tokens") or 0)
    cache_read = int(usage.get("cache_read_input_tokens") or 0)
    output = int(usage.get("output_tokens") or 0)
    return {
        "input_tokens": fresh + cache_write + cache_read,
        "cache_write_tokens": cache_write,
        "cache_read_tokens": cache_read,
        "output_tokens": output,
    }


def iter_assistant_usage(transcript_path: Path) -> list[tuple[str | None, str | None, dict[str, int]]]:
    """Return (uuid, model, normalized_usage) for each assistant usage block."""
    items: list[tuple[str | None, str | None, dict[str, int]]] = []
    if not transcript_path.exists():
        return items
    with transcript_path.open() as handle:
        for line in handle:
            line = line.strip()
            if not line or '"usage"' not in line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("type") != "assistant":
                continue
            message = record.get("message") or {}
            usage = message.get("usage") or record.get("usage")
            if not isinstance(usage, dict):
                continue
            normalized = normalize_claude_usage(usage)
            if not any(normalized.values()):
                continue
            uuid = record.get("uuid") or message.get("id")
            model = message.get("model") or record.get("model")
            items.append(
                (
                    str(uuid) if uuid else None,
                    str(model) if model else None,
                    normalized,
                )
            )
    return items


def sum_usage(items: list[tuple[str | None, str | None, dict[str, int]]]) -> dict[str, int]:
    totals = dict(EMPTY_USAGE)
    for _uuid, _model, usage in items:
        for key, value in usage.items():
            totals[key] = totals.get(key, 0) + value
    return totals


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"cumulative": dict(EMPTY_USAGE), "seen_uuids": []}
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {"cumulative": dict(EMPTY_USAGE), "seen_uuids": []}
    if not isinstance(data, dict):
        return {"cumulative": dict(EMPTY_USAGE), "seen_uuids": []}
    cumulative = data.get("cumulative") or {}
    merged = dict(EMPTY_USAGE)
    for key in EMPTY_USAGE:
        merged[key] = int(cumulative.get(key) or 0)
    seen = data.get("seen_uuids") or []
    if not isinstance(seen, list):
        seen = []
    return {"cumulative": merged, "seen_uuids": [str(x) for x in seen]}


def save_state(path: Path, state: dict) -> None:
    path.write_text(json.dumps(state, separators=(",", ":")) + "\n")


def usage_delta_from_transcript(
    transcript_path: Path | None, state_path: Path
) -> tuple[dict[str, int], str | None]:
    """Return (delta_usage, model) for new assistant usage since last state."""
    if transcript_path is None:
        return dict(EMPTY_USAGE), None

    state = load_state(state_path)
    seen = set(state.get("seen_uuids") or [])
    items = iter_assistant_usage(transcript_path)

    new_items: list[tuple[str | None, str | None, dict[str, int]]] = []
    for uuid, model, usage in items:
        if uuid and uuid in seen:
            continue
        new_items.append((uuid, model, usage))
        if uuid:
            seen.add(uuid)

    # Fallback when transcripts omit uuids: use cumulative totals.
    if not new_items and items:
        cumulative_now = sum_usage(items)
        previous = state.get("cumulative") or EMPTY_USAGE
        delta = {
            key: max(0, cumulative_now[key] - int(previous.get(key) or 0))
            for key in EMPTY_USAGE
        }
        model = items[-1][1]
        state["cumulative"] = cumulative_now
        save_state(state_path, state)
        return delta, model

    delta = sum_usage(new_items)
    model = new_items[-1][1] if new_items else None
    state["seen_uuids"] = list(seen)[-500:]
    state["cumulative"] = sum_usage(items)
    save_state(state_path, state)
    return delta, model


def refresh_project_report(project: Path) -> None:
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
            return 0

        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return 0

        root = project_root_from(payload)
        if root is None:
            return 0

        event = event_name(payload)
        hook_event = normalize_event(event)
        session_id = session_id_from(payload)
        log_dir = root / PROJECT_LOG_REL
        prepare_log_dir(log_dir)

        entry: dict = {
            "logged_at": utc_now(),
            "hook_event": hook_event,
            "hook_event_name": event,
            "session_id": session_id,
            "project": str(root),
            "log_dir": str(log_dir),
            "cwd": payload.get("cwd"),
            "permission_mode": payload.get("permission_mode"),
        }

        if hook_event == "stop":
            transcript = payload.get("transcript_path")
            transcript_path = Path(str(transcript)).expanduser() if transcript else None
            state_path = log_dir / f"{session_id}.state.json"
            delta, model = usage_delta_from_transcript(transcript_path, state_path)
            entry.update(delta)
            if model:
                entry["model"] = model
            entry["status"] = "completed"
            if transcript:
                entry["transcript_path"] = str(transcript)
        elif hook_event == "subagentStop":
            agent_transcript = payload.get("agent_transcript_path")
            transcript_path = (
                Path(str(agent_transcript)).expanduser() if agent_transcript else None
            )
            state_path = log_dir / f"{session_id}.subagents.state.json"
            delta, model = usage_delta_from_transcript(transcript_path, state_path)
            entry.update(delta)
            if model:
                entry["model"] = model
            entry["subagent_type"] = payload.get("agent_type")
            entry["agent_id"] = payload.get("agent_id")
            if agent_transcript:
                entry["agent_transcript_path"] = str(agent_transcript)
        elif hook_event == "preCompact":
            entry["trigger"] = payload.get("trigger")
        elif hook_event == "sessionEnd":
            entry["reason"] = payload.get("reason")

        log_path = log_dir / f"{session_id}.jsonl"
        with log_path.open("a") as handle:
            handle.write(json.dumps(entry, separators=(",", ":"), default=str) + "\n")

        if hook_event in ("stop", "sessionEnd"):
            refresh_project_report(root)

    except Exception:
        pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
