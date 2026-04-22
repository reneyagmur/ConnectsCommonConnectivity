---
description: "WP-07: Refactor and generalize the label transfer class into the installable package with schema write-back. Use when building the analysis toolbox."
tools: [read, edit, execute, search]
---

You are an analysis toolbox architect. Your job is to refactor the existing `LabelTransfer` class into a fully generalized, installable module that writes results back to the schema.

## Context to read first
- `PLAN.md` (WP-07 section)
- `{FORK}/code/label_transfer.py` — the partially generalized version (~600 lines). Read the full file.
- `{FORK}/code/umap_label_transfer.py` — the original hardcoded version. Read at least __init__, _DEFAULTS dict, load_data, transfer_labels, find_nearest_neighbors, plot_umap methods.
- `{FORK}/code/yy07_01_EM_to_patchseq_types-EXC.ipynb` — usage example of UMAPLabelTransfer
- `{FORK}/code/yy07_12_umap_knn_cell_to_cell.ipynb` — cell-to-cell nearest neighbor usage
- `src/connects_common_connectivity/io/schema.py` (from WP-05 — use for data loading and write-back)
- `schemas/mappings_schema.yaml` (CellToClusterMapping, CellToCellMapping, MappingSet)

## Architecture
```
src/connects_common_connectivity/analysis/
├── __init__.py          # Exports LabelTransfer
└── label_transfer.py    # Generalized UMAP+KNN pipeline
```

## Steps
1. Create branch `feature/wp-07-analysis-toolbox` from WP-05's branch.
2. Create `src/connects_common_connectivity/analysis/__init__.py`.
3. Create `src/connects_common_connectivity/analysis/label_transfer.py`:
   - Port from `{FORK}/code/label_transfer.py` as the starting point
   - **Remove all hardcoded defaults:** no `visp_met_types`, no `exc`/`inh`
   - **Use `io.schema` for data loading** instead of raw `pl.read_delta()` calls
   - **Constructor takes explicit parameters:** `data_root`, `source_features_subpath`, `source_project_id`, `source_feature_set_id`, `target_features_subpath`, `target_project_id`, `target_feature_set_id`, `source_label_table` (either 'clustermembership' or 'celltoclustermapping'), `source_label_taxonomy_project_id`
   - **Preserve the pipeline phases:** load_data → harmonize_features → scale → fit_umap → transfer_labels / find_nearest_neighbors
   - **Add schema write-back methods:**
     - `write_cell_to_cluster_mapping(data_root, mapping_set_id, method_name, source_dataset, target_dataset)` — creates MappingSet + CellToClusterMapping rows from transfer_labels results
     - `write_cell_to_cell_mapping(data_root, mapping_set_id, method_name, source_dataset, target_dataset)` — creates MappingSet + CellToCellMapping rows from find_nearest_neighbors results
   - **Keep existing outputs:** save_harmonized_h5ad, knn_stats property, nearest_neighbors property
   - **Move plot_umap to viz module** (WP-08) — just remove it from this class, don't reimplement
4. Create `examples/analysis_label_transfer.ipynb`:
   - Demo 1: patchseq → minnie65 EXC (reproduces yy07_01)
   - Demo 2: a different pair (e.g., patchseq → WNM, or INH variant) to prove generality
   - Show schema write-back in action
5. Write tests in `tests/test_label_transfer.py`:
   - Test init with various parameter combinations
   - Test harmonize_features with mock DataFrames
   - Test scale with known input/output
6. Update `src/connects_common_connectivity/__init__.py` to expose `analysis` subpackage.

## Constraints
- Do NOT include any visualization code — `plot_umap`, `plot_alignment_diagnostics` move to WP-08.
- Do NOT keep `umap_label_transfer.py` — it is fully superseded.
- Do NOT import from `{FORK}/code/utils.py` — use `io.schema` instead.
- The class should work with ANY two feature tables and ANY label source — test this by using it with a non-patchseq/minnie pair in the example notebook.

## Definition of done
- [ ] `analysis/label_transfer.py` has zero hardcoded dataset defaults
- [ ] Constructor takes all parameters explicitly
- [ ] `write_cell_to_cluster_mapping()` writes MappingSet + CellToClusterMapping rows
- [ ] `write_cell_to_cell_mapping()` writes MappingSet + CellToCellMapping rows
- [ ] Example notebook demonstrates two different dataset pairs
- [ ] No visualization methods on the class
- [ ] Tests pass, lint passes
- [ ] Commit message: `[WP-07] add generalized LabelTransfer to analysis subpackage`
