# PLAN — ConnectsCommonConnectivity Refactoring

This project defines a modular LinkML schema for integrating brain connectivity data across experimental modalities (EM, patch-seq, WNM morphology, barcoding, projections). We are refactoring from exploratory sandbox notebooks into a structured Python package with schema fixes, a data loading IO layer, a generalized analysis toolbox, and a modular visualization toolkit. Work is tracked as numbered work packages, each executed as a separate branch and PR.

## Work Packages

### WP-00 — Workspace & multi-root setup
- **Status:** [ ] not started
- **Objective:** Create a `.code-workspace` file with upstream repo as primary root and fork as read-only reference root.
- **Depends on:** none
- **Branch name:** n/a (local setup, no PR)
- **Acceptance criteria:**
  - `.code-workspace` file opens both roots in VS Code
  - Upstream repo is cloned separately or branched from `upstream/main`
  - `uv pip install -e ".[dev]"` works in the upstream root
  - Fork is accessible as second root for reference
- **Reference files from fork:**
  - `{FORK}/.github/copilot-instructions.md`
  - `{FORK}/pyproject.toml`

---

### WP-01 — Local data environment
- **Status:** [ ] not started
- **Objective:** Download combined delta lake datasets from CodeOcean and set up local paths mirroring the CodeOcean directory structure.
- **Depends on:** WP-00
- **Branch name:** n/a (local setup, no PR)
- **Acceptance criteria:**
  - `data/` directory mirrors `/root/capsule/data/` from CodeOcean
  - `scratch/combined_datasets/` mirrors `/scratch/combined_datasets/`
  - Environment variables `CCC_DATA_ROOT` and `CCC_SCRATCH_ROOT` are documented
  - A small test script verifies delta tables are readable with `polars.read_delta()`
- **Reference files from fork:**
  - `{FORK}/code/yy14_wnm_exc_vis_manuscript_dataset_dataitem.ipynb` (path constants pattern)
  - `{FORK}/code/yy05_combine_deltalakes_visp_microns.ipynb` (combined dataset structure)

---

### WP-02 — Schema: typo fix (`heirachy` → `hierarchy`)
- **Status:** [ ] not started
- **Objective:** Fix all misspellings of "hierarchy" in the clustering schema, regenerate models, update any Python code referencing the old names.
- **Depends on:** WP-00
- **Branch name:** `feature/wp-02-schema-typo-fix`
- **Acceptance criteria:**
  - `schemas/clustering_schema.yaml`: `heirachy_category` → `hierarchy_category`, `HierachyCategory` → `HierarchyCategory`, all description text corrected
  - `bash scripts/generate_models.sh` regenerates `models.py` cleanly
  - `uv run pytest` passes
  - `uv run ruff check src/ tests/` passes
  - No remaining instances of `heirachy` or `heirarchy` anywhere in the repo
- **Reference files from fork:**
  - `{FORK}/schemas/clustering_schema.yaml`
  - `{FORK}/src/connects_common_connectivity/models.py`
  - `{FORK}/SCHEMA_ISSUES.md` (issue #8)

---

### WP-03 — Schema: additive fields (#3+#7, #4, #10)
- **Status:** [ ] not started
- **Objective:** Add `cluster_project_id` and `taxonomy_version` for taxonomy identification (#3+#9), `feature_set_id` to `CellFeatureDefinition` (#4), `input_feature_set_id` to `CellToClusterMapping` (#7), and `Laterality` enum + `laterality` slot to `ProjectionMeasurementMatrix` (#10).
- **Depends on:** WP-02
- **Branch name:** `feature/wp-03-schema-additive-fields`
- **Acceptance criteria:**
  - `clustering_schema.yaml`: `Cluster` has optional `taxonomy_version` (string); `ClusterMembership` has optional `cluster_project_id` (string)
  - `cell_features_schema.yaml`: `CellFeatureDefinition` has optional `feature_set_id` (→ `CellFeatureSet`)
  - `mappings_schema.yaml`: `CellToClusterMapping` has optional `input_feature_set_id` (→ `CellFeatureSet`)
  - `base_schema.yaml`: new `Laterality` enum (`IPSILATERAL`, `CONTRALATERAL`, `BILATERAL`, `UNKNOWN`)
  - `projection_schema.yaml`: `ProjectionMeasurementMatrix` has optional `laterality` (→ `Laterality`)
  - `bash scripts/generate_models.sh` regenerates cleanly
  - `uv run pytest` passes (add tests for new fields)
  - `uv run ruff check src/ tests/` passes
- **Reference files from fork:**
  - `{FORK}/SCHEMA_ISSUES.md` (issues #3, #4, #7, #9, #10)
  - `{FORK}/schemas/clustering_schema.yaml`
  - `{FORK}/schemas/cell_features_schema.yaml`
  - `{FORK}/schemas/mappings_schema.yaml`
  - `{FORK}/schemas/base_schema.yaml`
  - `{FORK}/schemas/projection_schema.yaml`

---

### WP-04 — Schema: new classes (#11, #13)
- **Status:** [ ] not started
- **Objective:** Add `SampleMetadata` class for experimental metadata (#11) and a `ProjectionCoverage` representation for per-region binary flags (#13).
- **Depends on:** WP-03
- **Branch name:** `feature/wp-04-schema-new-classes`
- **Acceptance criteria:**
  - New `SampleMetadata` class (or extended `DataItem` slots) with `cre_line`, `animal_id`, `reporter_line`
  - Schema-level representation for projection coverage (design TBD: field on `ProjectionMeasurementMatrix` or standalone class)
  - Models regenerated, tests pass
- **Reference files from fork:**
  - `{FORK}/SCHEMA_ISSUES.md` (issues #11, #13)
  - `{FORK}/code/yy14_wnm_exc_vis_manuscript_dataset_dataitem.ipynb` (cre_line data)
  - `{FORK}/schemas/projection_schema.yaml`
  - `{FORK}/schemas/core_schema.yaml`

---

### WP-05 — Data loading IO module
- **Status:** [ ] not started
- **Objective:** Create `src/connects_common_connectivity/io/` subpackage with `schema.py` (read/write delta lake schema tables) and `readers.py` (convenience readers for raw experimental data).
- **Depends on:** WP-02
- **Branch name:** `feature/wp-05-data-io`
- **Acceptance criteria:**
  - `src/connects_common_connectivity/io/__init__.py` exports public API
  - `io/schema.py` contains at minimum:
    - `get_leaf_type_df(data_root, table, filter_value, ...)` — from clustermembership or celltoclustermapping
    - `read_feature_table(data_root, sub_path, project_id, feature_set_id)` — cellfeatures loader
    - `read_cluster_table(data_root, project_id)` — cluster table loader
    - `read_projection_matrix(data_root, matrix_id)` — projection matrix + wide-form data
    - `write_cell_feature_matrix_pointer(data_root, feature_set_id, parquet_path, ...)` — auto-write CellFeatureMatrix row
  - `io/readers.py` contains at minimum:
    - `read_csv_normalized(path, id_column, strip_suffix)` — CSV reader with ID normalization
    - `read_h5ad_features(path)` — h5ad → DataFrame convenience
  - All functions accept `data_root` as first argument (no hardcoded paths)
  - Tests with mock/fixture data in `tests/`
  - Functions are imported and usable: `from connects_common_connectivity.io import get_leaf_type_df`
- **Reference files from fork:**
  - `{FORK}/code/yy11_01_big_vis.ipynb` (cells 3, 11–12: `get_leaf_type_df`, `read_feats`)
  - `{FORK}/code/yy12_01_demo.ipynb` (cells 5, 17–25: same helpers duplicated)
  - `{FORK}/code/label_transfer.py` (lines 150–220: `_load_features`, `_load_labels`)
  - `{FORK}/code/umap_label_transfer.py` (lines 185–280: `load_patchseq_features`, `load_patchseq_labels`)
  - `{FORK}/src/connects_common_connectivity/parquet_loader.py`
  - `{FORK}/src/connects_common_connectivity/arrow_utils.py`

---

### WP-06 — ETL ingestion notebooks
- **Status:** [ ] not started
- **Objective:** Create clean example ETL notebooks demonstrating data-into-schema ingestion, including CellFeatureMatrix pointer writes and projection coverage flag computation.
- **Depends on:** WP-03, WP-05
- **Branch name:** `feature/wp-06-etl-notebooks`
- **Acceptance criteria:**
  - `examples/etl_wnm_exc_vis_manuscript.ipynb` — WNM dataset ingestion (features, projections, reconstructions)
  - `examples/etl_patchseq_visp.ipynb` — patchseq dataset ingestion (morph features, taxonomy mappings)
  - Each notebook writes `CellFeatureMatrix` pointer rows via `io.schema.write_cell_feature_matrix_pointer()`
  - Each notebook with projection data computes and writes the coverage binary flag
  - Notebooks use `io.readers` for CSV loading and `io.schema` for delta lake writes
  - No `sys.path.append` hacks — import from the installed package
  - Each notebook has a markdown header documenting source data, schema classes used, and output tables
- **Reference files from fork:**
  - `{FORK}/code/yy14_wnm_exc_vis_manuscript_dataset_dataitem.ipynb` (full WNM ingestion)
  - `{FORK}/code/yy05_combine_deltalakes_visp_microns.ipynb` (combining datasets)
  - `{FORK}/code/patchseq_and_wnm_datasets.ipynb` (patchseq ingestion)
  - `{FORK}/src/connects_common_connectivity/arrow_utils.py` (`build_arrow_schema`, `models_to_table`, `attach_linkml_metadata`)

---

### WP-07 — Analysis toolbox (generalized label transfer)
- **Status:** [ ] not started
- **Objective:** Refactor `LabelTransfer` into the installable package, remove hardcoded defaults, add schema write-back for mapping results.
- **Depends on:** WP-05
- **Branch name:** `feature/wp-07-analysis-toolbox`
- **Acceptance criteria:**
  - `src/connects_common_connectivity/analysis/__init__.py` exports `LabelTransfer`
  - `src/connects_common_connectivity/analysis/label_transfer.py` — generalized class:
    - No hardcoded `visp_met_types`, `exc`/`inh`, `patchseq`/`minnie` defaults
    - All dataset parameters are explicit constructor arguments
    - Label source is configurable (any column, or loaded from clustermembership/celltoclustermapping via `io.schema`)
    - `write_cell_to_cluster_mapping(data_root, mapping_set_id, ...)` — writes results as `CellToClusterMapping` rows
    - `write_cell_to_cell_mapping(data_root, mapping_set_id, ...)` — writes nearest-neighbor results as `CellToCellMapping` rows
    - Existing functionality preserved: scale, harmonize, fit_umap, transfer_labels, find_nearest_neighbors, save_h5ad
  - `examples/analysis_label_transfer.ipynb` — demonstrates usage with two different dataset pairs
  - `umap_label_transfer.py` is NOT carried forward (superseded)
  - Tests for the class pipeline (at minimum: init, harmonize, scale)
- **Reference files from fork:**
  - `{FORK}/code/label_transfer.py` (generalized version, ~600 lines)
  - `{FORK}/code/umap_label_transfer.py` (original version with exc/inh hardcoding)
  - `{FORK}/code/yy07_01_EM_to_patchseq_types-EXC.ipynb` (usage example)
  - `{FORK}/code/yy07_11_umap_knn_label_transfer_with_scores.ipynb` (knn scores)
  - `{FORK}/code/yy07_12_umap_knn_cell_to_cell.ipynb` (cell-to-cell neighbors)

---

### WP-08 — Visualization toolbox
- **Status:** [ ] not started
- **Objective:** Create `src/connects_common_connectivity/viz/` subpackage with modular plotting functions, each returning `(fig, axes)` and designed for future ipywidgets wrapping.
- **Depends on:** WP-05
- **Branch name:** `feature/wp-08-viz-toolbox`
- **Acceptance criteria:**
  - `src/connects_common_connectivity/viz/__init__.py` exports public API
  - `viz/strips.py`:
    - `plot_strips(df, strips, sort_by, ...)` — sorted cell-strip figure for features + category labels
    - `merge_strips(id_col, *specs)` — inner-join helper for composing strip data
  - `viz/adjacency.py`:
    - `adjacencyplot(adjacency, nodes, ...)` — scatter/heatmap for connectivity matrices (square + long-form)
    - `AxisGrid` class for appending group axes
  - `viz/projections.py`:
    - `plot_projection_heatmap(matrix_df, region_order, ...)` — heatmap for projection data
  - `viz/umap.py`:
    - `plot_umap_scatter(embeddings, labels, colors, ...)` — UMAP embedding with cluster coloring
  - Every plot function returns `(fig, axes)` or `(fig, grid)` tuple
  - Parameters that will become dropdown selections are typed as enums or `list[str]`
  - No data loading inside plot functions — accept DataFrames only
  - `examples/plots_cross_modal_demo.ipynb` — demonstrates composing multiple plot types
  - `examples/plots_connectivity.ipynb` — adjacency plot examples
- **Reference files from fork:**
  - `{FORK}/code/yy12_01_demo.ipynb` (cell 5: `plot_strips`, `merge_strips`, `stretch_to_match`)
  - `{FORK}/code/yy11_01_big_vis.ipynb` (cells 17–29: strip plotting + composition)
  - `{FORK}/code/utils.py` (`adjacencyplot`, `AxisGrid`, `draw_bracket`, `draw_box`)
  - `{FORK}/code/umap_label_transfer.py` (`plot_umap` method, ~lines 700+)
  - `{FORK}/code/yy11_02_big_vis_connectome oriented.ipynb` (connectivity visualization)

---

## Execution Order

```
Phase 0 (setup):      WP-00, WP-01               — parallel, no PRs
Phase 1 (breaking):   WP-02                       — schema typo fix
Phase 2 (parallel):   WP-03 + WP-05              — schema additive + IO module
Phase 3 (parallel):   WP-04 + WP-06 + WP-07      — new classes + ETL + analysis
Phase 4:              WP-08                        — visualization
```

WP-05 can start as soon as WP-02 is merged (needs correct field names).
WP-03 and WP-05 have no dependency on each other and can run in parallel.
WP-06 needs both WP-03 (schema fields) and WP-05 (io functions).
WP-07 and WP-08 only need WP-05.

## Conventions

- **Branch naming:** `feature/wp-XX-short-description`
- **Commit messages:** `[WP-XX] short description` (e.g., `[WP-02] fix hierarchy typo in clustering schema`)
- **Notebook naming:** `examples/etl_{dataset}.ipynb`, `examples/analysis_{name}.ipynb`, `examples/plots_{topic}.ipynb`
- **Sandbox notebooks:** `code/sandbox/` (gitignored or explicitly experimental)
- **Package structure:** New modules go in `src/connects_common_connectivity/{subpackage}/`
- **No `sys.path.append`:** All imports via the installed package
- **Schema workflow:** Edit YAML → `bash scripts/generate_models.sh` → `uv run pytest` → commit both YAML and generated `models.py`
- **Path constants:** All functions take `data_root` as explicit parameter; no hardcoded `/scratch/` or `/root/capsule/` paths
- **Plot functions:** Return `(fig, axes)` tuple; accept DataFrames, not paths; parameters for future dropdowns typed as enums/lists
