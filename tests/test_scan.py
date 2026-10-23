"""Tests for the stale-branch classification."""

from pathlib import Path

from branchshred.scan import scan_all, scan_repo


def test_merged_branch_is_candidate(messy_repo: Path):
    report = scan_repo(messy_repo, older_than_days=90, extra_protected=frozenset())
    by_name = {c.name: c for c in report.candidates}
    assert by_name["feature-done"].merged is True


def test_stale_unmerged_branch_is_candidate(messy_repo: Path):
    report = scan_repo(messy_repo, older_than_days=90, extra_protected=frozenset())
    by_name = {c.name: c for c in report.candidates}
    assert by_name["feature-abandoned"].merged is False
    assert by_name["feature-abandoned"].days_old >= 90


def test_fresh_unmerged_branch_is_not_candidate(messy_repo: Path):
    report = scan_repo(messy_repo, older_than_days=90, extra_protected=frozenset())
    assert "feature-wip" not in {c.name for c in report.candidates}


def test_default_and_current_never_candidates(messy_repo: Path):
    report = scan_repo(messy_repo, older_than_days=0, extra_protected=frozenset())
    # even with a zero-day threshold, main must never show up
    assert "main" not in {c.name for c in report.candidates}


def test_extra_protected_branches_skipped(messy_repo: Path):
    report = scan_repo(messy_repo, older_than_days=90, extra_protected=frozenset({"feature-abandoned"}))
    assert "feature-abandoned" not in {c.name for c in report.candidates}


def test_older_than_threshold_is_respected(messy_repo: Path):
    strict = scan_repo(messy_repo, older_than_days=365, extra_protected=frozenset())
    names = {c.name for c in strict.candidates}
    assert "feature-abandoned" not in names  # only 120d old
    assert "feature-done" in names  # merged branches ignore age


def test_candidates_sorted_merged_first_then_oldest(messy_repo: Path):
    report = scan_repo(messy_repo, older_than_days=90, extra_protected=frozenset())
    names = [c.name for c in report.candidates]
    assert names[0] == "feature-done"  # merged sorts before unmerged
    assert names[1] == "feature-abandoned"


def test_clean_repo_has_no_candidates(repos_folder: Path):
    clean = repos_folder / "clean"
    report = scan_repo(clean, older_than_days=90, extra_protected=frozenset())
    assert report.candidates == []
    assert report.total_branches == 1


def test_scan_all_skips_broken_repo_but_keeps_good_ones(tmp_path: Path, messy_repo: Path):
    # a .git file pointing nowhere: find_repos sees it, git can't use it
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / ".git").write_text("gitdir: /does/not/exist\n")
    reports = scan_all([broken, messy_repo], older_than_days=90, extra_protected=frozenset())
    assert [r.repo.name for r in reports] == [messy_repo.name]
