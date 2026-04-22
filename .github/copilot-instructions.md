# Copilot Instructions — ConnectsCommonConnectivity

## Project overview
Modular LinkML schema for integrating mouse brain connectivity data across experimental modalities (EM, patch-seq, WNM morphology, barcoding, projections). Generates Pydantic v2 models from schema and provides data loading, analysis, and visualization tools.

## Source of truth
- **PLAN.md** in repo root defines all work packages, dependencies, and conventions.
- The **forked repo** (second workspace root, if present) contains reference implementations in `code/`.
- **SCHEMA_ISSUES.md** tracks active schema design issues and their triage status.

## Commands
```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
uv run pytest -q
uv run ruff check src/ tests/
uv run mypy src/
bash scripts/generate_models.sh   # after any schema YAML edit
```

## Package structure
```
schemas/                              # LinkML YAML (source of truth)
src/connects_common_connectivity/
├── models.py                         # AUTO-GENERATED — never edit by hand
├── arrow_utils.py                    # Pydantic → PyArrow bridge
├── parquet_loader.py                 # Parquet → Pydantic ETL
├── io/                               # Data loading layer
│   ├── schema.py                     # Read/write delta lake schema tables
│   └── readers.py                    # Raw data reading utilities
├── analysis/                         # Derived data tools
│   └── label_transfer.py            # Generalized UMAP+KNN label transfer
└── viz/                              # Visualization modules
    ├── strips.py                     # Feature/category strip plots
    ├── adjacency.py                  # Connectivity matrix plots
    ├── projections.py                # Projection heatmaps
    └── umap.py                       # UMAP scatter plots
examples/                             # Clean notebooks (etl_*, analysis_*, plots_*)
tests/
```

## Key conventions
- **Schema edits:** Edit the module YAML, not the aggregator. Run `generate_models.sh`, then pytest, then commit both.
- **No sys.path.append.** Import from the installed package.
- **All functions take `data_root` as explicit parameter.** No hardcoded paths.
- **Plot functions return `(fig, axes)`.** Accept DataFrames, not file paths.
- **Commit format:** `[WP-XX] short description` when working on a work package.
- **Branch format:** `feature/wp-XX-short-description`

## Schema notes
- `models.py` is auto-generated from `schemas/` via `gen-pydantic`.
- `ProjectScoped` mixin adds `project_id` to scoped classes.
- `ClusterMembership` = dataset defines taxonomy. `CellToClusterMapping` = mapped to external taxonomy.
- DataItem `id` is shared across projects by design (cross-modal join key).
- See `SCHEMA_ISSUES.md` for active schema issues and their triage status.

## Testing
- Tests in `tests/test_basic.py`. Pattern: instantiate models with valid/invalid data.
- Use `pytest.raises(Exception)` for constraint violations.
- New modules should have corresponding test files.
