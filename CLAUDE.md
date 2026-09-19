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

One setup step per clone, beside `uv sync` — nothing forces it, so it is the
only part worth stating here:

```
npm install
```

It installs a dev-only npm layer (husky + `@casomoltd/tooling`) whose sole job
is to run the shared commitlint rules on every commit message, and a pre-push
hook that runs `ruff`, `pyright` and `pytest`. uv remains the toolchain; there
is deliberately no `npm run check`.

**The commit rules themselves are not restated here.** They live in
`@casomoltd/tooling/commitlint` and the hook names whichever one you broke.
Copying them into this file would put one rule in two places, and this file
would be the copy that goes stale.

## Working style

- **Phase large changes.** When a change has a mechanical part and a
  design-heavy part, do the mechanical one first and re-plan the harder one
  separately, rather than proposing one combined plan. The hard part reliably
  needs more design attention than a combined plan gives it.
- **Leave the commit to David** unless he asks. Work lands in the working tree;
  `git diff` is the review surface and the decision is his.
