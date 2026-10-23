# branchshred

[![python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![tests](https://img.shields.io/badge/tests-30%20passing-brightgreen)](#testing)

Point it at a folder full of git repos. It finds every stale branch — merged ones and long-dead unmerged ones — and shreds them. Dry run by default, because deleting branches on a Friday afternoon should require intent.

```
$ branchshred ~/dev

my-bot  (default: main, 14 branches)
  [merged ] feature-old-welcome  — last commit 211d ago
  [merged ] fix-rate-limit        — last commit 96d ago
  [stale  ] experiment-voice      — last commit 143d ago

dotfiles  (default: master, 6 branches)
  [merged ] temp-nvim-config     — last commit 320d ago

5 stale branch(es): 4 merged, 1 unmerged-stale.
Dry run — nothing deleted. Re-run with --prune to delete merged branches.
Unmerged branches also need --force (that's the dangerous one).
```

## Why I built this

I keep all my side projects in one folder, and every few months I'd open it and find dozens of dead branches — feature branches merged months ago, experiments I abandoned, `temp-fix-2` from a 2am session. Cleaning them meant cd-ing into each repo and running `git branch --merged` by hand, which I never did, so they just piled up.

branchshred is the Sunday-cleaning version of that chore: one command, every repo, and it won't delete anything until you explicitly tell it to.

## Install

```bash
pip install git+https://github.com/codewithkrrish/branchshred.git
```

Needs Python 3.9+ and git on your PATH. Zero dependencies.

## Usage

```bash
# scan the current folder's repos (dry run — deletes nothing)
branchshred

# scan a folder of repos
branchshred ~/dev

# scan a single repo
branchshred ~/dev/my-bot

# actually delete the merged branches
branchshred ~/dev --prune

# also delete unmerged stale branches (the dangerous one)
branchshred ~/dev --prune --force

# unmerged branches older than 30 days count as stale
branchshred ~/dev --older-than 30

# never touch these, no matter what
branchshred ~/dev --prune --protected release --protected hotfix-keep

# machine-readable output
branchshred ~/dev --json
```

## How it decides what's stale

A branch is a candidate when **all** of these hold:

1. It's not your currently checked-out branch.
2. It's not the default branch (`main`/`master` are always protected, plus whatever `--protected` you pass).
3. It's either fully merged into the default branch (any age — the work already landed), or unmerged but untouched for longer than `--older-than` days (default 90).

And how deletion works:

| Branch type | `--prune` | `--prune --force` |
|---|---|---|
| Merged | deleted via `git branch -d` (git double-checks it's really merged) | deleted |
| Unmerged stale | skipped, listed by name | deleted via `git branch -D` |

No flag combination deletes silently — without `--prune` it's always a dry run.

## Limitations (honest ones)

- Only scans the folder you point at plus its immediate subdirectories — no deep recursion. My `~/dev` is flat; if yours is nested three deep this won't find everything.
- "Stale" is a heuristic, not a truth. A 200-day-old unmerged branch might be your magnum opus. That's why unmerged deletes need `--force` and merged ones use git's own `-d` safety check.
- Default-branch detection guesses: remote's HEAD, then `main`, then `master`, then current branch. Exotic setups (multiple mainlines, `develop` as main) may need `--protected` to keep the right branches safe.
- One weird repo (corrupt `.git`, mid-rebase) is skipped silently in normal output rather than aborting the whole scan.

## Project structure

```
branchshred/
  __init__.py    version
  cli.py         argparse + output formatting (thin layer)
  errors.py      human-readable exceptions, no tracebacks
  git.py         subprocess wrappers around git
  scan.py        the stale-branch classification logic
  prune.py       deletion with the safety rails
tests/
  conftest.py    builds real throwaway git repos
  test_git.py    git wrapper behavior
  test_scan.py   classification rules
  test_prune_cli.py  safety rails + CLI exit codes
```

## License

MIT — see [LICENSE](LICENSE).

## Author

[Krrish](https://github.com/codewithkrrish) — I build Discord bots and small dev tools. If branchshred saved you from branch hell, a star is appreciated.
