# Kallim Project Instructions

## Environment

Manage the environment with uv (the venv lives at `.venv/`):

- Sync deps: `uv sync`
- Run commands: `uv run <cmd>` — e.g. `uv run kallim lint`, `uv run pyright`,
  `uv run ruff check`, `uv run pytest`
- Add a dependency: `uv add <package>` (`uv add --dev <package>` for tooling)
- Never call `pip` directly or edit `requirements*.txt`; `pyproject.toml` and
  `uv.lock` are the source of truth.

## Commits

- Do not include AI attribution or Co-Authored-By lines in commit messages

## Working style

- **Phase large changes.** When a change has a mechanical part and a
  design-heavy part, do the mechanical one first and re-plan the harder one
  separately, rather than proposing one combined plan. The hard part reliably
  needs more design attention than a combined plan gives it.
- **Leave the commit to David** unless he asks. Work lands in the working tree;
  `git diff` is the review surface and the decision is his.
