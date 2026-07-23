#!/usr/bin/env python3
"""Print a text usage report for a session from project hook logs.

Looks only in <project>/.cursor/usage-logs/ (cwd by default).

Usage:
  report-usage.py              # list recent sessions in cwd project
  report-usage.py --latest     # print latest session report
  report-usage.py <session_id> # print that session report
  report-usage.py --latest --rebuild
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

PROJECT_LOG_REL = Path(".cursor") / "usage-logs"
SCRIPT_DIR = Path(__file__).resolve().parent


def load_logger():
    path = SCRIPT_DIR / "log-usage.py"
    spec = importlib.util.spec_from_file_location("cursor_log_usage", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def project_log_dir(project: Path | None = None) -> Path:
    root = project or Path.cwd()
    return root / PROJECT_LOG_REL


def sessions_from_dir(log_dir: Path) -> list[Path]:
    if not log_dir.exists():
        return []
    return sorted(
        (p for p in log_dir.glob("*.jsonl") if p.name != "sessions-index.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Cursor session usage reports")
    parser.add_argument("session_id", nargs="?", help="Session / conversation id")
    parser.add_argument(
        "--latest", action="store_true", help="Show the most recent session report"
    )
    parser.add_argument(
        "--list", action="store_true", help="List recent session log files"
    )
    parser.add_argument(
        "--project",
        type=Path,
        default=None,
        help="Project root (default: cwd)",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild the report from JSONL before printing",
    )
    args = parser.parse_args()

    log_dir = project_log_dir(args.project)
    sessions = sessions_from_dir(log_dir)

    list_mode = args.list or (not args.session_id and not args.latest)
    if list_mode:
        if not sessions:
            print("No session logs found.")
            print(f"  Project logs: {log_dir}")
            print("Logs appear after agent turns once the plugin hooks are active.")
            return 0

        print(f"Recent sessions ({log_dir}):\n")
        for path in sessions[:30]:
            report = path.with_name(f"{path.stem}-report.txt")
            marker = "report" if report.exists() else "jsonl only"
            print(f"  {path.stem}  ({marker})")
        print("\nRun: report-usage.py --latest")
        print("  or: report-usage.py <session_id>")
        return 0

    if args.latest:
        if not sessions:
            print("No session logs found.")
            return 1
        log_path = sessions[0]
        session_id = log_path.stem
    else:
        session_id = args.session_id
        log_path = log_dir / f"{session_id}.jsonl"
        if not log_path.exists():
            print(f"No log for session: {session_id}")
            print(f"  Looked in: {log_dir}")
            return 1

    report_path = log_path.with_name(f"{session_id}-report.txt")

    if args.rebuild or not report_path.exists():
        logger = load_logger()
        logger.write_report(session_id, log_path)

    if report_path.exists():
        print(report_path.read_text(), end="")
        return 0

    print(f"Could not build report for {session_id}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
