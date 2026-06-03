---
name: commit
description: >-
  Type-check with pyright, stage changes, and commit
user-invocable: true
argument-hint: "[message]"
allowed-tools:
  - Bash(pyright *)
  - Bash(.venv/bin/pyright *)
  - Bash(git *)
---

# Kallim Commit Workflow

Follow these steps in order. Do NOT skip or reorder steps.

## 1. Run type checks

```bash
.venv/bin/pyright
```

Must pass with zero errors. If it fails, fix the issues and
re-run until it passes. Do NOT proceed until it passes.

## 2. Stage changed files

Stage files explicitly by name. **Never** use `git add -A` or
`git add .` — always list specific files.

Review what you are staging with `git diff --stat` first.

## 3. Check for remaining unstaged changes

After staging, run `git diff --stat` to see if there are
**other** uncommitted changes in the working tree. If there
are related changes that should go out together, make
**multiple commits first** (repeat steps 2–4 for each batch).

## 4. Show diff and wait for approval

Run `git diff --staged` and present it to the user. **Stop and
wait for the user to approve** before committing. Do NOT
proceed until the user explicitly confirms the diff is OK.

## 5. Commit

Create a commit with a concise message:
- **Header**: max 50 characters, imperative mood
- **Body** (optional): wrap at 72 characters, explain WHY
- **No AI attribution** — no "Co-Authored-By" or
  "Generated with Claude Code" lines
- **Issue reference**: if the conversation mentions an
  issue number, include a `Closes #<number>` or
  `Refs #<number>` footer. Don't prompt for one if
  it's not already in context.

If `$ARGUMENTS` contains a message, use it as the commit
message.

## 6. Done

Do **not** push automatically. The user will push when ready.

## Error recovery

When something goes wrong, **never** use destructive git
commands to "fix" it. No `git reset --hard`,
`git push --force`, or history rewrites.

- **Pre-commit hook fails after staging:** Fix the issue
  and create a **new** commit — never amend.
- **Push fails:** Investigate the cause and resolve without
  rewriting history.
