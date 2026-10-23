"""Shared fixtures: throwaway git repos built for real.

These spin up actual git repositories (not mocks) because branchshred's
whole job is reading git state — mocking git would test nothing useful.
Everything lives under pytest's tmp_path so nothing escapes.
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

TEST_ENV = {
    "GIT_AUTHOR_NAME": "branchshred-test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "branchshred-test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
    # keep the machine's real gitconfig out of the tests
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
}


def git(repo: Path, *args: str, days_ago: int = 0) -> str:
    env = dict(os.environ, **TEST_ENV)
    if days_ago:
        # backdate both author and committer stamps with an absolute date —
        # git's relative date parsing is pickier than it looks
        stamp = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
        env["GIT_AUTHOR_DATE"] = stamp
        env["GIT_COMMITTER_DATE"] = stamp
    proc = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, env=env, timeout=30
    )
    assert proc.returncode == 0, f"git {' '.join(args)} failed: {proc.stderr}"
    return proc.stdout.strip()


def init_repo(path: Path, branch: str = "main") -> Path:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-b", branch, "-q")
    return path


def commit(repo: Path, filename: str, *, days_ago: int = 0, message: str = "work") -> None:
    (repo / filename).write_text(f"{message}\n")
    git(repo, "add", filename)
    git(repo, "commit", "-qm", message, days_ago=days_ago)


@pytest.fixture
def messy_repo(tmp_path: Path) -> Path:
    """A repo with every branch flavor: merged, stale-unmerged, fresh, main.

    main            <- checked out, the default
    feature-done    <- merged into main, last touched 200d ago
    feature-abandoned <- unmerged, last touched 120d ago
    feature-wip     <- unmerged, touched today
    """
    repo = init_repo(tmp_path / "messy")
    commit(repo, "a.txt", message="first")

    git(repo, "checkout", "-qb", "feature-done")
    commit(repo, "b.txt", message="done work", days_ago=200)
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "-q", "--no-ff", "feature-done", "-m", "merge done")

    git(repo, "checkout", "-qb", "feature-abandoned")
    commit(repo, "c.txt", message="abandoned work", days_ago=120)

    git(repo, "checkout", "-qb", "feature-wip")
    commit(repo, "d.txt", message="wip")

    git(repo, "checkout", "-q", "main")
    return repo


@pytest.fixture
def repos_folder(tmp_path: Path, messy_repo: Path) -> Path:
    """A folder holding one messy repo, one clean repo, and one non-repo dir."""
    clean = init_repo(tmp_path / "repos" / "clean")
    commit(clean, "x.txt", message="only main here")
    (tmp_path / "repos" / "not-a-repo").mkdir(parents=True, exist_ok=True)
    (tmp_path / "repos" / "not-a-repo" / "notes.txt").write_text("hello\n")
    messy_target = tmp_path / "repos" / "messy"
    messy_repo.rename(messy_target)
    return tmp_path / "repos"
