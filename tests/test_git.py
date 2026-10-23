"""Tests for the git wrappers."""

from pathlib import Path

import pytest

from branchshred import git as gitmod
from branchshred.errors import GitFailedError
from conftest import commit, git, init_repo


def test_find_repos_scans_subdirectories(repos_folder: Path):
    repos = gitmod.find_repos(repos_folder)
    assert {r.name for r in repos} == {"messy", "clean"}


def test_find_repos_ignores_plain_folders(tmp_path: Path):
    (tmp_path / "empty").mkdir()
    assert gitmod.find_repos(tmp_path) == []


def test_find_repos_prefers_root_repo_itself(messy_repo: Path):
    assert gitmod.find_repos(messy_repo) == [messy_repo]


def test_default_branch_prefers_main(messy_repo: Path):
    assert gitmod.default_branch(messy_repo) == "main"


def test_default_branch_falls_back_to_master(tmp_path: Path):
    repo = init_repo(tmp_path / "old", branch="master")
    commit(repo, "a.txt")
    assert gitmod.default_branch(repo) == "master"


def test_default_branch_falls_back_to_current(tmp_path: Path):
    repo = init_repo(tmp_path / "weird", branch="dev")
    commit(repo, "a.txt")
    assert gitmod.default_branch(repo) == "dev"


def test_local_branches_empty_on_fresh_repo(tmp_path: Path):
    repo = init_repo(tmp_path / "fresh")
    assert gitmod.local_branches(repo) == []


def test_local_branches_reports_commit_times(messy_repo: Path):
    branches = dict(gitmod.local_branches(messy_repo))
    assert set(branches) == {"main", "feature-done", "feature-abandoned", "feature-wip"}
    assert branches["feature-abandoned"] < branches["feature-wip"]  # older commit


def test_merged_branches_lists_only_merged(messy_repo: Path):
    merged = gitmod.merged_branches(messy_repo, "main")
    assert "feature-done" in merged
    assert "feature-abandoned" not in merged
    assert "feature-wip" not in merged


def test_git_failure_raises_human_error(tmp_path: Path):
    (tmp_path / "nope").mkdir()
    with pytest.raises(GitFailedError) as excinfo:
        gitmod.local_branches(tmp_path / "nope")
    assert "nope" in str(excinfo.value)  # repo name in the message, no traceback needed
