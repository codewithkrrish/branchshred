"""Deleting branches, with the safety rails on.

Two paths:
  - merged branches: `git branch -d` — git itself refuses if the branch isn't
    really merged, so even a misclassification can't lose work here.
  - unmerged stale branches: only with --force, via `git branch -D`. This is
    the one that can lose commits, so it needs the user to say it twice:
    --prune --force.

Without --prune everything is a dry run: we report what WOULD happen and
touch nothing. There is no flag combination that deletes silently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import git
from .errors import GitFailedError
from .scan import ScanReport, StaleBranch


@dataclass
class PruneResult:
    deleted: list[StaleBranch] = field(default_factory=list)
    skipped_unmerged: list[StaleBranch] = field(default_factory=list)
    failed: list[tuple[StaleBranch, str]] = field(default_factory=list)


def plan_prune(reports: list[ScanReport], *, force: bool) -> tuple[list[StaleBranch], list[StaleBranch]]:
    """Split candidates into (will delete, will skip). No side effects."""
    doomed, skipped = [], []
    for report in reports:
        for branch in report.candidates:
            if branch.merged or force:
                doomed.append(branch)
            else:
                skipped.append(branch)
    return doomed, skipped


def prune(reports: list[ScanReport], *, force: bool, dry_run: bool) -> PruneResult:
    """Execute (or dry-run) the prune plan. Returns what happened."""
    result = PruneResult()
    doomed, skipped = plan_prune(reports, force=force)
    result.skipped_unmerged = skipped
    if dry_run:
        return result  # nothing touched; deleted stays empty on purpose

    # group by repo so each git call lands in the right directory
    by_repo: dict[str, tuple[Path, list[StaleBranch]]] = {}
    for branch in doomed:
        report = next(r for r in reports if r.repo.name == branch.repo)
        by_repo.setdefault(branch.repo, (report.repo, []))[1].append(branch)

    for _name, (repo_path, branches) in by_repo.items():
        for branch in branches:
            try:
                # merged -> safe -d; unmerged only reachable with force -> -D
                git.delete_branch(repo_path, branch.name, force=not branch.merged and force)
                result.deleted.append(branch)
            except GitFailedError as exc:
                result.failed.append((branch, str(exc)))
    return result
