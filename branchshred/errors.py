"""Exception types with human-readable messages.

Every error the CLI can show a user comes from here, so nothing ever
leaks a raw traceback — branchshred is a janitor, not a debugger.
"""


class BranchshredError(Exception):
    """Base for all branchshred failures shown to the user."""


class NoReposError(BranchshredError):
    """Raised when no git repositories are found under the target folder."""


class GitFailedError(BranchshredError):
    """A git subprocess exited non-zero. Carries git's own stderr."""

    def __init__(self, repo: str, command: list[str], stderr: str) -> None:
        self.repo = repo
        self.command = command
        super().__init__(f"{repo}: git {' '.join(command)} failed: {stderr.strip() or 'unknown error'}")
