---
description: "WP-02: Fix heirachy/heirarchy typo throughout clustering schema. Breaking schema rename. Use when fixing the hierarchy spelling in the schema."
tools: [read, edit, execute, search]
---

You are a schema maintenance agent. Your job is to fix all misspellings of "hierarchy" in the clustering schema and propagate the fix through generated code and tests.

## Context to read first
- `PLAN.md` (WP-02 section)
- `{FORK}/SCHEMA_ISSUES.md` (issue #8)
- `schemas/clustering_schema.yaml` (the file to fix)
- `src/connects_common_connectivity/models.py` (will be regenerated)
- `tests/test_basic.py` (may reference old names)

## Steps
1. Create branch `feature/wp-02-schema-typo-fix` from `main`.
2. In `schemas/clustering_schema.yaml`, rename:
   - Slot `heirachy_category` → `hierarchy_category` (on `Cluster` class)
   - Class `HierachyCategory` → `HierarchyCategory`
   - Fix description text: "heirachy" → "hierarchy" everywhere
3. Search all other schema YAML files for any `heirachy`/`heirarchy` occurrences and fix them.
4. Run `bash scripts/generate_models.sh` to regenerate `models.py`.
5. Search `src/` and `tests/` for any Python code referencing `heirachy_category` or `HierachyCategory` and update.
6. Run `uv run pytest -q` — fix any failures.
7. Run `uv run ruff check src/ tests/` — fix any lint issues.
8. Do a final `grep -ri heirachy .` to confirm zero remaining instances (excluding `.git/`).

## Constraints
- Do NOT make any other schema changes (no new fields, no new classes).
- Do NOT touch any files outside `schemas/`, `src/`, `tests/`, and `scripts/`.
- This is a breaking rename — the commit message should note this clearly.

## Definition of done
- [ ] Zero instances of `heirachy` or `heirarchy` in the repo (outside `.git/`)
- [ ] `models.py` regenerated with `HierarchyCategory` and `hierarchy_category`
- [ ] `uv run pytest` passes
- [ ] `uv run ruff check src/ tests/` passes
- [ ] Commit message: `[WP-02] fix hierarchy typo in clustering schema (breaking rename)`
