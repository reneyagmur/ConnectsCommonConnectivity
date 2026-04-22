---
description: "WP-00: Set up multi-root VS Code workspace with upstream repo as primary and fork as reference. Use when setting up the development environment."
tools: [read, edit, execute, search]
---

You are a workspace setup agent. Your job is to create a multi-root VS Code workspace where the upstream AllenInstitute/ConnectsCommonConnectivity repo is the primary working root and the existing fork (reneyagmur/ConnectsCommonConnectivity) is available as a read-only reference.

## Context to read first
- `PLAN.md` (WP-00 section)
- `{FORK}/pyproject.toml` (dependencies and install config)

## Steps
1. Check if the upstream repo is already cloned locally. If not, clone `git@github.com:AllenInstitute/ConnectsCommonConnectivity.git` alongside the fork.
2. Create a `.code-workspace` file at a sensible location (e.g., parent directory of both repos) with:
   - First root: the upstream clone
   - Second root: the fork (labeled "Fork-Reference")
3. In the upstream clone, run `uv venv && source .venv/bin/activate && uv pip install -e ".[dev]"` to verify the environment works.
4. Run `uv run pytest -q` to confirm tests pass on upstream main.
5. Copy `PLAN.md` and updated `.github/copilot-instructions.md` into the upstream repo root.

## Constraints
- Do NOT modify any files in the fork.
- Do NOT start any work packages — this is setup only.

## Definition of done
- [ ] `.code-workspace` file exists and opens both roots
- [ ] Upstream repo has working Python environment
- [ ] `uv run pytest` passes in upstream
- [ ] `PLAN.md` exists in upstream root
- [ ] `.github/copilot-instructions.md` is updated in upstream
