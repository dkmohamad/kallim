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
