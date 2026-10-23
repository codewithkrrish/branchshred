"""Deciding which branches are stale. This is the whole brain of the tool.

A branch is a shred candidate when it is:
  1. not the branch you have checked out right now,
  2. not the default branch (and not main/master by name, just in case the
     default detection guessed wrong), and not user-protected,
  3. either fully merged into the default branch (any age — it's done), or
     unmerged but untouched for longer than --older-than days.

Rule 3's second half is deliberately conservative: an unmerged branch might
still hold work someone cares about, so age alone never marks it for the
safe delete path. Pruning those needs an extra --force, always.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from . import git

# Branch names that are never candidates, even if default-branch detection
# somehow picked something else. Cheap insurance.
_ALWAYS_PROTECTED = frozenset({"main", "master"})


@dataclass(frozen=True)
class StaleBranch:
    repo: str      # folder name of the repository
    name: str
    merged: bool   # fully merged into the default branch
    days_old: int  # days since its last commit


@dataclass
class ScanReport:
    repo: Path
    default_branch: str
    candidates: list[StaleBranch] = field(default_factory=list)
    total_branches: int = 0

    @property
    def merged_count(self) -> int:
        return sum(1 for c in self.candidates if c.merged)

    @property
    def unmerged_count(self) -> int:
        return sum(1 for c in self.candidates if not c.merged)


def scan_repo(repo: Path, *, older_than_days: int, extra_protected: frozenset[str]) -> ScanReport:
    """Scan one repo and return its shred candidates."""
    now = int(time.time())
    cutoff_days = older_than_days

    default = git.default_branch(repo)
    current = git.current_branch(repo)
    protected = _ALWAYS_PROTECTED | {default} | set(extra_protected)

    branches = git.local_branches(repo)
    merged = git.merged_branches(repo, default)

    report = ScanReport(repo=repo, default_branch=default, total_branches=len(branches))
    for name, last_commit_ts in branches:
        if name == current or name in protected:
            continue
        days_old = max(0, (now - last_commit_ts) // 86_400)
        is_merged = name in merged
        if is_merged or days_old >= cutoff_days:
            report.candidates.append(
                StaleBranch(repo=repo.name, name=name, merged=is_merged, days_old=days_old)
            )
    # deterministic output: merged first, then oldest first
    report.candidates.sort(key=lambda c: (not c.merged, -c.days_old))
    return report


def scan_all(
    repos: list[Path], *, older_than_days: int, extra_protected: frozenset[str]
) -> list[ScanReport]:
    """Scan every repo. A repo that fails to scan is skipped, not fatal."""
    reports = []
    for repo in repos:
        try:
            reports.append(
                scan_repo(repo, older_than_days=older_than_days, extra_protected=extra_protected)
            )
        except Exception:
            # One weird repo (corrupt, mid-rebase, whatever) shouldn't kill
            # a scan of twenty others. The CLI reports it in verbose mode.
            # TODO: collect these into the report so --json can surface them.
            continue
    return reports
