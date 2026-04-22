---
description: "WP-05: Create data loading IO module with schema readers/writers and raw data readers. Use when building the io subpackage for delta lake and experimental data loading."
tools: [read, edit, execute, search]
---

You are a data IO architect. Your job is to create the `io/` subpackage that provides clean functions for reading from and writing to the delta lake schema, plus convenience readers for raw experimental data.

## Context to read first
- `PLAN.md` (WP-05 section)
- `{FORK}/code/yy11_01_big_vis.ipynb` — read cells 3 and 11–12 for `get_leaf_type_df()` and `read_feats()` implementations
- `{FORK}/code/yy12_01_demo.ipynb` — read cell 5 for the duplicated helpers: `get_leaf_type_df`, `read_feats`, `merge_strips`, `lookup_patchseq_neighbors`, `stretch_to_match`
- `{FORK}/code/label_transfer.py` — read lines 150–230 for `_load_features()` and `_load_labels()`
- `{FORK}/code/umap_label_transfer.py` — read lines 185–280 for the patchseq/minnie-specific loading
- `{FORK}/src/connects_common_connectivity/parquet_loader.py` — existing generic loader
- `{FORK}/src/connects_common_connectivity/arrow_utils.py` — existing arrow utilities

## Architecture
```
src/connects_common_connectivity/io/
├── __init__.py          # Re-exports public API
├── schema.py            # Functions for reading/writing delta lake schema tables
└── readers.py           # Convenience for reading raw experimental data (CSV, h5ad)
```

**`io/schema.py`** talks ONLY to the delta lake. Input: `data_root` path + filters. Output: polars or pandas DataFrames.

**`io/readers.py`** talks to raw files (CSV, h5ad). Used only in ETL notebooks. No delta lake awareness.

## Steps
1. Create branch `feature/wp-05-data-io` from WP-02's branch (needs corrected `hierarchy_category` name).
2. Create `src/connects_common_connectivity/io/__init__.py`.
3. Create `src/connects_common_connectivity/io/schema.py` with these functions (generalized from fork reference):

   **`get_leaf_type_df(data_root, table, filter_value, filter_col='project_id', id_col=None, label_col=None, cluster_project_id=None, cast_id_to_int=True) -> pd.DataFrame`**
   - Loads cell→cluster assignments from `clustermembership` or `celltoclustermapping`
   - Joins cluster table to find deepest (leaf) assignment per cell
   - Returns DataFrame with columns `['id', 'predicted_label']`
   - Reference: `{FORK}/code/yy11_01_big_vis.ipynb` cell 3

   **`get_all_typed_cells(data_root, cluster_project_id, project_ids=None) -> pd.DataFrame`**
   - Queries BOTH `clustermembership` AND `celltoclustermapping` for all cells assigned to clusters in a given taxonomy
   - Returns unified DataFrame with `['id', 'predicted_label', 'source_table']`
   - This is a NEW function the user specifically requested

   **`read_feature_table(data_root, sub_path, project_id=None, feature_set_id=None, id_is_int=True) -> pd.DataFrame`**
   - Loads a `cellfeatures/*` delta table with optional filters
   - Reference: `read_feats()` in `{FORK}/code/yy11_01_big_vis.ipynb` cell 12

   **`read_cluster_table(data_root, project_id=None) -> pd.DataFrame`**
   - Loads cluster table with optional project_id filter

   **`read_projection_matrix(data_root, matrix_id) -> tuple[pd.DataFrame, pd.DataFrame]`**
   - Returns (metadata_row, wide_form_data) for a ProjectionMeasurementMatrix

   **`write_cell_feature_matrix_pointer(data_root, feature_set_id, parquet_path, cell_index_column='id', project_id=None) -> None`**
   - Writes a CellFeatureMatrix row linking a CellFeatureSet to its physical data path

4. Create `src/connects_common_connectivity/io/readers.py` with:

   **`read_csv_normalized(path, id_column=None, strip_suffix='.swc', **read_csv_kwargs) -> pd.DataFrame`**
   - Reads CSV, normalizes index/ID column by stripping suffix
   - Reference: ID normalization pattern in `{FORK}/code/yy14_wnm_exc_vis_manuscript_dataset_dataitem.ipynb` cell 10

   **`read_h5ad_features(path) -> pd.DataFrame`**
   - Loads h5ad and returns obs + X as a flat DataFrame

5. Update `src/connects_common_connectivity/__init__.py` to expose `io` subpackage.
6. Write tests in `tests/test_io.py`:
   - Test `get_leaf_type_df` with a small mock delta table (use pyarrow + tempdir)
   - Test `read_csv_normalized` with a temp CSV file
7. Run `uv run pytest -q` and `uv run ruff check src/ tests/`.

## Constraints
- All functions take `data_root` as first argument. ZERO hardcoded paths.
- `io/schema.py` uses `polars.read_delta()` for reading, `deltalake.write_deltalake()` for writing.
- `io/readers.py` uses `pandas` for CSV, `anndata` for h5ad (optional import).
- Do NOT put visualization code here.
- Do NOT put analysis/ML code here.
- Keep `merge_strips` and `stretch_to_match` OUT of io — they belong in viz (WP-08).

## Definition of done
- [ ] `io/schema.py` has all 6 functions listed above
- [ ] `io/readers.py` has `read_csv_normalized` and `read_h5ad_features`
- [ ] `io/__init__.py` re-exports public functions
- [ ] `from connects_common_connectivity.io import get_leaf_type_df` works
- [ ] Tests pass for at least `get_leaf_type_df` and `read_csv_normalized`
- [ ] `uv run pytest` passes, `uv run ruff check` passes
- [ ] Commit message: `[WP-05] add io subpackage with schema readers/writers and raw data readers`
