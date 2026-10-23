"""Command-line interface. Deliberately thin: parse args, call scan/prune, print.

Exit codes: 0 = ok, 1 = runtime problem (no repos, git blew up, a delete
failed), 2 = bad flags (argparse handles that one itself).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .errors import BranchshredError
from . import git
from .prune import prune
from .scan import ScanReport, scan_all

EXIT_OK = 0
EXIT_ERROR = 1

DEFAULT_OLDER_THAN_DAYS = 90


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="branchshred",
        description="Find stale git branches across every repo in a folder — and prune them safely.",
    )
    p.add_argument("folder", nargs="?", default=".",
                   help="folder to scan (default: current directory). If it is itself a git repo, only it is scanned.")
    p.add_argument("--older-than", type=int, default=DEFAULT_OLDER_THAN_DAYS, metavar="DAYS",
                   help=f"unmerged branches older than DAYS count as stale (default: {DEFAULT_OLDER_THAN_DAYS})")
    p.add_argument("--prune", action="store_true",
                   help="actually delete. Without this, branchshred only reports (dry run).")
    p.add_argument("--force", action="store_true",
                   help="also delete unmerged stale branches (git branch -D). Needs --prune too.")
    p.add_argument("--protected", action="append", default=[], metavar="NAME",
                   help="extra branch name to never touch (repeatable)")
    p.add_argument("--json", action="store_true",
                   help="machine-readable output instead of the human report")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def _human_report(reports: list[ScanReport], *, pruning: bool, force: bool) -> str:
    lines: list[str] = []
    total = 0
    for report in reports:
        if not report.candidates:
            continue
        total += len(report.candidates)
        lines.append(f"\n{report.repo.name}  (default: {report.default_branch}, {report.total_branches} branches)")
        for c in report.candidates:
            tag = "merged " if c.merged else "stale  "
            lines.append(f"  [{tag}] {c.name}  — last commit {c.days_old}d ago")
    if total == 0:
        lines.append("Nothing stale. Your branches are suspiciously tidy.")
        return "\n".join(lines)

    merged = sum(r.merged_count for r in reports)
    unmerged = total - merged
    lines.append(f"\n{total} stale branch(es): {merged} merged, {unmerged} unmerged-stale.")
    if not pruning:
        lines.append("Dry run — nothing deleted. Re-run with --prune to delete merged branches.")
        if unmerged:
            lines.append("Unmerged branches also need --force (that's the dangerous one).")
    return "\n".join(lines)


def _json_report(reports: list[ScanReport]) -> str:
    payload = [
        {
            "repo": r.repo.name,
            "default_branch": r.default_branch,
            "total_branches": r.total_branches,
            "candidates": [
                {"name": c.name, "merged": c.merged, "days_since_last_commit": c.days_old}
                for c in r.candidates
            ],
        }
        for r in reports
    ]
    return json.dumps(payload, indent=2)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.older_than < 0:
        print("error: --older-than can't be negative", file=sys.stderr)
        return EXIT_ERROR
    if args.force and not args.prune:
        print("error: --force does nothing without --prune (dry runs delete nothing)", file=sys.stderr)
        return EXIT_ERROR

    root = Path(args.folder).expanduser().resolve()
    if not root.is_dir():
        print(f"error: not a folder: {args.folder}", file=sys.stderr)
        return EXIT_ERROR

    repos = git.find_repos(root)
    if not repos:
        print(f"error: no git repositories found under {root}", file=sys.stderr)
        print("hint: point branchshred at a folder containing your repos, or at one repo directly",
              file=sys.stderr)
        return EXIT_ERROR

    try:
        reports = scan_all(
            repos,
            older_than_days=args.older_than,
            extra_protected=frozenset(args.protected),
        )
    except BranchshredError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if args.json:
        print(_json_report(reports))
        return EXIT_OK

    print(_human_report(reports, pruning=args.prune, force=args.force))

    if args.prune:
        result = prune(reports, force=args.force, dry_run=False)
        if result.deleted:
            print(f"\nDeleted {len(result.deleted)} branch(es).")
        if result.skipped_unmerged:
            names = ", ".join(f"{b.repo}/{b.name}" for b in result.skipped_unmerged)
            print(f"Skipped {len(result.skipped_unmerged)} unmerged branch(es) (needs --force): {names}")
        for branch, why in result.failed:
            print(f"Couldn't delete {branch.repo}/{branch.name}: {why}", file=sys.stderr)
        if result.failed:
            return EXIT_ERROR
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
