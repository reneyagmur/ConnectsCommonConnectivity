# Copilot Instructions — ConnectsCommonConnectivity

## Project Overview

This project defines a **modular LinkML schema** for integrating brain connectivity data across experimental modalities (EM synaptic connectivity, cell morphology, patch-seq, barcoding, projection measurements). It generates Pydantic v2 models from the schema and provides a generic Parquet→Pydantic ETL loader. The domain is mouse brain single-axon resolution data (pilot: visual cortex, VISp), targeting cross-modal comparison.

## Commands

```bash
# Install
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# Tests
uv run pytest -q                              # full suite
uv run pytest tests/test_basic.py::test_import -v  # single test

# Lint / type check
uv run ruff check src/ tests/
uv run mypy src/

# Regenerate Pydantic models after schema edits
bash scripts/generate_models.sh
# (equivalent to: gen-pydantic schemas/connectivity_schema.yaml > src/connects_common_connectivity/models.py)
```

## Architecture

### Schema (source of truth)

`schemas/` contains modular LinkML YAML files. `connectivity_schema.yaml` is the aggregator that imports all modules:

| Module | Contents |
|--------|----------|
| `base_schema.yaml` | Enums (Modality, etc.), type overrides, prefixes |
| `core_schema.yaml` | DataSet, DataItem, ProjectScoped mixin |
| `brain_region_schema.yaml` | BrainRegion hierarchy |
| `clustering_schema.yaml` | AlgorithmRun, ClusterHierarchy, Cluster, ClusterMembership |
| `projection_schema.yaml` | ProjectionMeasurement classes |
| `cell_features_schema.yaml` | CellFeatureSet, Definition, Matrix, Measurement |
| `mappings_schema.yaml` | MappingSet, Cell↔Cell/Cluster, Cluster↔Cluster mappings |
| `cell_gene_schema.yaml` | CellGeneData, BarcodingExperimentMetadata |
| `single_cell_schema.yaml` | SingleCellReconstruction |
| `cell_cell_schema.yaml` | Cell-cell connectivity matrices |
| `zarr_schema.yaml` | ZarrArray, ZarrDataset, ParquetDataset |

### Python package (`src/connects_common_connectivity/`)

- **`models.py`** — Auto-generated Pydantic v2 classes. **Never edit by hand.** Regenerate with `generate_models.sh`.
- **`__init__.py`** — Exports `generate_pydantic_models()` (dynamic generation) and `get_schema_path()`.
- **`parquet_loader.py`** — Generic Parquet→Pydantic loader; two-phase: instantiate all objects first, then resolve object references.
- **`arrow_utils.py`** — PyArrow utilities: normalize enums/nested models, infer Arrow schema from Pydantic models.
- **`cli.py`** — CLI entry point: `ccc info`, `ccc bundle`, `ccc validate`, `ccc etl-brain-regions`.

### Brain region ontologies

- `brain_regions.yaml` — BrainRegion list with `descendants: null` (sparse, ~23K lines)
- `brain_regions_generic.yaml` — Same with `descendants` fully populated (~32K lines)

Both are derived from Allen Institute `terminology.parquet` via `examples/etl_brain_regions.py`.

## Key Conventions

### Schema authoring

- Edit the module closest to your change (not the aggregator).
- Use `inlined: false` on slots whose `range` is another class when you want ID references (not nested objects).
- Use `aliases` on slots to declare alternative Parquet column names — the ETL uses these for auto-mapping, not hard-coded heuristics.
- Use the `ProjectScoped` mixin (adds `project_id`) for any class that lives within a project scope; uniqueness is `(project_id, id)`.
- Slot constraints available: `required`, `multivalued`, `minimum_value`, `maximum_value`, `pattern` (regex).

### Model generation workflow

After any schema change:
1. Run `bash scripts/generate_models.sh` to regenerate `models.py`.
2. Run `uv run pytest` to validate the updated models.
3. The generated file is committed; dynamic generation via `generate_pydantic_models()` is used at runtime during development.

### ETL / data loading

- `parquet_loader.py` performs two passes: first instantiate all objects with raw IDs, then resolve cross-references.
- Unresolved references produce warnings, not hard failures — check loader output when loading relational data.
- Multivalued slots handle Parquet list types, JSON strings, and comma-separated strings automatically.

### Testing patterns

Tests live in `tests/test_basic.py`. Pattern: instantiate models with valid/invalid data, use `pytest.raises(Exception)` for constraint violations (required fields, enum values, numeric bounds like probability ∈ [0,1]).

### Known schema design issues

See `SCHEMA_ISSUES.md` for 7 active issues with proposed resolutions, including:
- DataItem IDs not globally unique (use composite `project_id + id` key)
- ClusterMembership vs. CellToClusterMapping inconsistency (deprecate ClusterMembership)
- CellFeatureDefinition ID collisions (namespace by featureset)

Before adding new classes/slots that touch clustering, cell features, or mapping relationships, review `SCHEMA_ISSUES.md` to avoid compounding these issues.
