"""Thin wrappers around the git CLI.

I shell out to git instead of parsing .git internals by hand on purpose:
reading packfiles myself is how you get subtle, repo-corrupting bugs, and
a janitor tool must never corrupt. subprocess is slower, but boring and
correct — a trade-off I'm fine with for something that runs interactively.

Every function here takes a repo Path and raises GitFailedError with git's
own stderr when something goes wrong, so callers never see raw
CalledProcessError.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .errors import GitFailedError

# for-each-ref fields are joined with the ASCII unit separator: branch names
# can't contain control characters, so this is unambiguous — and unlike NUL
# it's legal inside a subprocess argv.
_SEP = "\x1f"


def _run(repo: Path, *args: str) -> str:
    """Run git in repo, return stripped stdout. Raise GitFailedError on failure."""
    proc = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0:
        raise GitFailedError(repo.name, list(args), proc.stderr)
    return proc.stdout.strip()


def find_repos(root: Path) -> list[Path]:
    """Return git repos to scan.

    If root itself is a repo, just it. Otherwise the immediate subdirectories
    that contain a .git entry (files count too — worktrees use a .git file,
    not a directory). Non-git folders are ignored silently.
    """
    if (root / ".git").exists():
        return [root]
    repos = [d for d in sorted(root.iterdir()) if d.is_dir() and (d / ".git").exists()]
    return repos


def current_branch(repo: Path) -> str | None:
    """Name of the checked-out branch, or None if detached/unborn."""
    try:
        name = _run(repo, "branch", "--show-current")
    except GitFailedError:
        return None
    return name or None


def local_branches(repo: Path) -> list[tuple[str, int]]:
    """All local branches as (name, last-commit-unix-time) pairs."""
    out = _run(repo, "for-each-ref", f"--format=%(refname:short){_SEP}%(committerdate:unix)", "refs/heads/")
    if not out:
        return []  # fresh repo, no commits yet — nothing to shred
    result = []
    for line in out.splitlines():
        name, _, ts = line.partition(_SEP)
        try:
            result.append((name, int(ts)))
        except ValueError:
            continue  # shouldn't happen; skip rather than crash the scan
    return result


def branch_exists(repo: Path, name: str) -> bool:
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{name}"],
        cwd=repo, capture_output=True, timeout=30,
    )
    return proc.returncode == 0


def default_branch(repo: Path) -> str:
    """Best guess at the repo's mainline branch.

    Order: origin's HEAD (if there's a remote) -> local main -> local master
    -> whatever is checked out. The last fallback keeps single-branch repos
    usable instead of erroring out.
    """
    try:
        ref = _run(repo, "symbolic-ref", "refs/remotes/origin/HEAD")
        # looks like refs/remotes/origin/main
        name = ref.rsplit("/", 1)[-1]
        if name and branch_exists(repo, name):
            return name
    except GitFailedError:
        pass  # no remote or no origin/HEAD — fall through to local guesses
    for guess in ("main", "master"):
        if branch_exists(repo, guess):
            return guess
    current = current_branch(repo)
    if current:
        return current
    raise GitFailedError(repo.name, ["symbolic-ref"], "could not determine a default branch")


def merged_branches(repo: Path, base: str) -> set[str]:
    """Names of local branches fully merged into base."""
    out = _run(repo, "branch", "--merged", base, "--format=%(refname:short)")
    return {line for line in out.splitlines() if line}


def delete_branch(repo: Path, name: str, *, force: bool = False) -> None:
    """Delete a local branch. Safe -d for merged, -D only when forced."""
    flag = "-D" if force else "-d"
    _run(repo, "branch", flag, name)
