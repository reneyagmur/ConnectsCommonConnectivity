---
description: "WP-03: Add taxonomy identification, feature definition namespacing, mapping featureset tracking, and laterality enum to schema. Use when adding new fields to existing schema classes."
tools: [read, edit, execute, search]
---

You are a schema evolution agent. Your job is to add new optional fields and enums to existing schema classes, addressing issues #3, #4, #7, and #10 from SCHEMA_ISSUES.md.

## Context to read first
- `PLAN.md` (WP-03 section)
- `{FORK}/SCHEMA_ISSUES.md` (issues #3, #4, #7, #10)
- `schemas/clustering_schema.yaml` (Cluster, ClusterMembership)
- `schemas/cell_features_schema.yaml` (CellFeatureDefinition)
- `schemas/mappings_schema.yaml` (CellToClusterMapping)
- `schemas/base_schema.yaml` (enums)
- `schemas/projection_schema.yaml` (ProjectionMeasurementMatrix)

## Steps
1. Create branch `feature/wp-03-schema-additive-fields` from the tip of WP-02's branch.
2. **Issue #3 + #9 — Taxonomy identification:**
   - In `clustering_schema.yaml`, add optional `taxonomy_version` (range: string) slot to `Cluster`
   - Add optional `cluster_project_id` (range: string) slot to `ClusterMembership` with description: "project_id of the taxonomy the cluster belongs to, when different from the cell's project_id"
3. **Issue #4 — Feature definition namespacing:**
   - In `cell_features_schema.yaml`, add optional `feature_set_id` (range: CellFeatureSet) slot to `CellFeatureDefinition`
4. **Issue #7 — Per-cell featureset tracking:**
   - In `mappings_schema.yaml`, add optional `input_feature_set_id` (range: CellFeatureSet) slot to `CellToClusterMapping`
5. **Issue #10 — Laterality:**
   - In `base_schema.yaml`, add `Laterality` enum with values: `IPSILATERAL`, `CONTRALATERAL`, `BILATERAL`, `UNKNOWN`
   - In `projection_schema.yaml`, add optional `laterality` (range: Laterality) slot to `ProjectionMeasurementMatrix`
6. Run `bash scripts/generate_models.sh` to regenerate `models.py`.
7. Add tests in `tests/test_basic.py` for the new fields (instantiate models with and without the new optional fields).
8. Run `uv run pytest -q` and `uv run ruff check src/ tests/`.

## Constraints
- All new fields must be OPTIONAL (not required) to maintain backward compatibility.
- Do NOT create new classes — only add fields/enums.
- Do NOT modify `models.py` by hand.
- Do NOT touch `io/`, `analysis/`, or `viz/` code.

## Definition of done
- [ ] All four issues addressed with optional fields
- [ ] `Laterality` enum exists in `base_schema.yaml`
- [ ] `models.py` regenerated with new fields
- [ ] Tests cover instantiation with new fields
- [ ] `uv run pytest` passes
- [ ] `uv run ruff check src/ tests/` passes
- [ ] Commit message: `[WP-03] add taxonomy_version, cluster_project_id, feature_set_id, input_feature_set_id, laterality`
