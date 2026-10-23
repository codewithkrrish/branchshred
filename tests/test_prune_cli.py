"""Tests for pruning safety and the CLI."""

import json
from pathlib import Path

import pytest

from branchshred import cli
from branchshred import git as gitmod


def branch_names(repo: Path) -> set[str]:
    return {name for name, _ in gitmod.local_branches(repo)}


def test_dry_run_deletes_nothing(messy_repo: Path, capsys):
    code = cli.main([str(messy_repo)])
    assert code == 0
    out = capsys.readouterr().out
    assert "Dry run" in out
    assert branch_names(messy_repo) == {"main", "feature-done", "feature-abandoned", "feature-wip"}


def test_prune_deletes_only_merged(messy_repo: Path, capsys):
    code = cli.main([str(messy_repo), "--prune"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Deleted 1" in out
    assert "feature-done" not in branch_names(messy_repo)
    # unmerged stale branch survives without --force
    assert "feature-abandoned" in branch_names(messy_repo)


def test_prune_force_also_deletes_unmerged_stale(messy_repo: Path):
    code = cli.main([str(messy_repo), "--prune", "--force"])
    assert code == 0
    remaining = branch_names(messy_repo)
    assert remaining == {"main", "feature-wip"}


def test_force_without_prune_is_an_error(messy_repo: Path, capsys):
    code = cli.main([str(messy_repo), "--force"])
    assert code == 1
    assert "--force does nothing without --prune" in capsys.readouterr().err


def test_negative_older_than_is_an_error(messy_repo: Path, capsys):
    assert cli.main([str(messy_repo), "--older-than", "-5"]) == 1


def test_no_repos_found_is_an_error(tmp_path: Path, capsys):
    assert cli.main([str(tmp_path)]) == 1
    assert "no git repositories" in capsys.readouterr().err


def test_missing_folder_is_an_error(capsys):
    assert cli.main(["/does/not/exist"]) == 1


def test_bad_flag_exits_2(messy_repo: Path):
    with pytest.raises(SystemExit) as excinfo:
        cli.main([str(messy_repo), "--bogus"])
    assert excinfo.value.code == 2


def test_json_output_parses(messy_repo: Path, capsys):
    code = cli.main([str(messy_repo), "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["repo"] == messy_repo.name
    candidates = {c["name"]: c for c in payload[0]["candidates"]}
    assert candidates["feature-done"]["merged"] is True
    assert candidates["feature-abandoned"]["merged"] is False


def test_protected_flag_keeps_branch(messy_repo: Path):
    code = cli.main([str(messy_repo), "--prune", "--force",
                     "--protected", "feature-abandoned"])
    assert code == 0
    assert "feature-abandoned" in branch_names(messy_repo)
    assert "feature-done" not in branch_names(messy_repo)


def test_prune_failure_reports_and_exits_1(messy_repo: Path, monkeypatch, capsys):
    # simulate git refusing a delete mid-prune: the CLI must report it on
    # stderr and exit 1, not dump a traceback
    from branchshred.errors import GitFailedError

    def boom(repo: Path, name: str, *, force: bool = False) -> None:
        raise GitFailedError(repo.name, ["branch", "-d", name], "simulated refusal")

    monkeypatch.setattr(gitmod, "delete_branch", boom)
    code = cli.main([str(messy_repo), "--prune"])
    assert code == 1
    assert "Couldn't delete" in capsys.readouterr().err
