---
description: "WP-04: Add SampleMetadata class and ProjectionCoverage schema representation. Use when adding new schema classes for experimental metadata and projection coverage. Lower priority."
tools: [read, edit, execute, search]
---

You are a schema design agent. Your job is to add new schema classes for experimental sample metadata and projection coverage flags.

## Context to read first
- `PLAN.md` (WP-04 section)
- `{FORK}/SCHEMA_ISSUES.md` (issues #11, #13)
- `{FORK}/code/yy14_wnm_exc_vis_manuscript_dataset_dataitem.ipynb` (cell 2 markdown: cre_line data described; cells 23–26: SingleCellReconstruction pattern)
- `schemas/core_schema.yaml` (DataItem, DataSet)
- `schemas/projection_schema.yaml` (ProjectionMeasurementMatrix)
- `schemas/brain_region_schema.yaml` (BrainRegion)

## Steps
1. Create branch `feature/wp-04-schema-new-classes` from WP-03's branch.
2. **Issue #11 — SampleMetadata:**
   - Decide: new class vs. extending DataItem. Recommendation: new class `SampleMetadata` in `core_schema.yaml` (or a new `sample_metadata_schema.yaml`) with:
     - `id` (identifier)
     - `dataitem_id` (range: DataItem, required)
     - `cre_line` (string, optional)
     - `animal_id` (string, optional)
     - `reporter_line` (string, optional)
   - Add `ProjectScoped` mixin
3. **Issue #13 — Projection coverage:**
   - Add optional `region_coverage` slot to `ProjectionMeasurementMatrix` (multivalued bool, parallel to `region_index`)
   - Description: "Binary flag per region indicating whether any cell in the dataset has non-zero projection to that region. Computed by toolkit."
4. Import any new schema modules into `connectivity_schema.yaml` (the aggregator).
5. Run `bash scripts/generate_models.sh`, then pytest, then ruff.

## Constraints
- Keep both additions minimal — avoid over-engineering.
- `region_coverage` is computed by toolkit code (WP-06), not by the schema itself.
- Do NOT write any toolkit or ETL code — schema only.

## Definition of done
- [ ] `SampleMetadata` class exists in schema with cre_line, animal_id, reporter_line
- [ ] `region_coverage` field exists on `ProjectionMeasurementMatrix`
- [ ] Aggregator imports updated if new module added
- [ ] Models regenerated, tests pass, lint passes
- [ ] Commit message: `[WP-04] add SampleMetadata class and region_coverage field`
