# Contributing / Workflow Rules

This repo is built by a small AI team (team lead + researcher + developer sessions,
each a separate Claude Code instance) as a portfolio project. These rules exist so
the three of us don't collide with each other and so the repo stays safe to run.

## Scope guardrail

- Never read, write, or delete anything outside this repo directory
  (`C:\Users\mkuch\projects\askmycity` and its subfolders). No editing files
  elsewhere on the machine, no touching other projects, no changing global
  git/user config beyond what's already set in this repo.
- Never commit secrets. `ANTHROPIC_API_KEY` and any other credentials are read
  from the environment or `.streamlit/secrets.toml` (gitignored) — never hardcoded,
  never committed, never printed in full to logs/commit messages.

## Branching

- `main` is the integration branch. Nobody commits to `main` directly — it only
  moves via a merged PR.
- Each contributor works in their own **git worktree** on their own feature branch,
  so two sessions never have the same working directory pointed at different
  branches at once:
  - developer → `.worktrees/app-scaffold` on `feature/app-scaffold`
  - researcher → `.worktrees/data-scoping` on `feature/data-scoping`
- Branch names: `feature/<short-description>` (or `fix/...`, `chore/...`). No work
  directly on `main`.

## Commits

- Commit early and often — small, atomic commits over one giant commit. Each
  commit should leave the repo in a working state where reasonably possible.
- Conventional-commit-style messages: `feat: ...`, `fix: ...`, `docs: ...`,
  `test: ...`, `chore: ...`.

## Merging

- Push your branch and open a PR into `main` (via `gh pr create`) rather than
  merging locally. The team lead reviews and merges.
- No force-pushing shared branches, no `git push --force` to `main`, no history
  rewriting (`rebase -i`, `reset --hard` + force-push) on anything already pushed.
- Rebase/merge `main` into your feature branch to pick up others' merged work
  before opening your PR, if `main` has moved.

## Safety

- Don't run destructive commands (`git reset --hard`, `git clean -fdx`, deleting
  branches other than your own) without checking with the team lead first.
- Keep committed data small (well under 20MB) and license-checked — no scraped
  data of unclear license, no large raw dumps (see `data/DATA_DICTIONARY.md` once
  it exists).
