# Schema Issues & Action Items

## ~~1. DataItem IDs are not globally unique across combined datasets~~ [CLOSED]

**Resolution:** Not a bug. Shared DataItem IDs across projects are **by design** — they are the cross-modal join key that links the same physical cell across different datasets (e.g., cell `864691135571546917` appears in both `minnie65` and `visp_exc_patchseq`). The `project_id` scopes the dataset, not the cell identity. No schema change needed.

---

## ~~2. `ClusterMembership` and `CellToClusterMapping` model the same thing inconsistently~~ [CLOSED]

**Resolution:** Not a bug — the two classes have distinct semantics. `ClusterMembership` is for when a dataset *defines* a taxonomy and its cells belong to it natively (e.g., minnie65 CSM types). `CellToClusterMapping` is for when cells are *mapped* to an external taxonomy (e.g., minnie65 cells assigned to visp_met_types via label transfer). The inconsistency in some patchseq notebooks (using the wrong class) is a notebook-level bug, not a schema design issue. A toolkit function can query both classes to retrieve all cell-to-cluster assignments regardless of provenance.

---

## 3. Cluster and mapping records don't identify which taxonomy they refer to (includes versioning)

*Absorbs former issue 9 (`Cluster` table has no link to its source taxonomy version).*

**Problem — taxonomy ambiguity:** Cluster labels like `"Glutamatergic"` or `"L6b"` appear in multiple taxonomies (`minnie65`, `visp_met_types`, `tasic_2018_visp_scrnaseq`). In `ClusterMembership`, the `project_id` refers to the *cell's* project, not the cluster's taxonomy. `CellToClusterMapping` partially addresses this via `MappingSet.target_dataset`, but only when `MappingSet` is present and populated.

**Problem — taxonomy versioning:** `Cluster` rows are scoped only by `project_id`. The same project can release multiple taxonomy versions over time (e.g., CCN20230722, v1.0), and there is no field to distinguish them. A consumer cannot tell which release a cluster belongs to without external knowledge.

**Possible directions (to discuss):**
- Add optional `taxonomy_version` string to `Cluster` → solves versioning
- Add `cluster_project_id` to `ClusterMembership` → solves cross-taxonomy ambiguity for native memberships
- Rely on existing `MappingSet.target_dataset` for `CellToClusterMapping` and only fix `ClusterMembership` — since native membership implies the cluster's `project_id` matches the membership's `project_id`, ambiguity only arises with versioning
- Long-term: link `Cluster` to `AlgorithmRun` / `ClusterHierarchy` (ties back to issue 5)

---

## 4. `CellFeatureDefinition` IDs are not namespaced and will collide across featuresets

**Problem:** A feature named `total_length` in `minnie_exc_skel_keys` and `total_length` in a patchseq featureset have the same `id` in the schema. The current workaround is Delta Lake sub-path partitioning (`cellfeaturedefinition/minnie_exc_skel_keys/`), but nothing in the schema prevents collisions in a combined flat table.

**Action:** Namespace feature definition IDs by featureset at the schema level (e.g. `minnie_exc_skel_keys:total_length`), or add `feature_set_id` as a required field on `CellFeatureDefinition` and make `(feature_set_id, id)` the composite key.

---

## 5. `AlgorithmRun` and `ClusterHierarchy` are never written, and `AlgorithmRun` has no link to a featureset

**Problem:** These classes exist in `clustering_schema.yaml` and are intended to capture provenance — which algorithm, on which input, produced a given taxonomy. In practice, no `AlgorithmRun` or `ClusterHierarchy` records are ever written; `Cluster` nodes are written directly, partitioned only by `project_id`. Additionally, `AlgorithmRun.input_dataset` points to a `DataSet`, but the same dataset can have multiple featuresets — so it is impossible to record which featureset was the actual input to the clustering run.

**Action:** Add an `input_feature_set` slot (→ `CellFeatureSet`) to `AlgorithmRun`. Then write `AlgorithmRun` + `ClusterHierarchy` records when ingesting each taxonomy (e.g. in `process_patchseq_taxonomy_info.ipynb`). If that is out of scope for now, remove these classes until they are ready to be used.

---

## ~~6. No schema mechanism for a combined/derived featureset~~ [CLOSED — deferred]

**Resolution:** Not needed for current work. The feature harmonization step in the label transfer toolkit handles intersection/alignment of feature sets at runtime without requiring schema-level composition. Can revisit if a persistent, published combined featureset becomes necessary.

---

## 7. Cells within the same dataset may use different featuresets (or feature subsets) when being mapped to the same clusterset

**Problem:** `AlgorithmRun.input_feature_set` (proposed in item 5) assumes one featureset per run, but this doesn't hold when cells in the same dataset have heterogeneous features. The concrete case: Minnie65 EXC cells use `minnie_exc_skel_keys` and INH cells use `minnie_inh_skel_keys`, but both are assigned to the same taxonomy. If patchseq EXC and INH datasets were ever merged into one, the same problem would apply there too. The featureset used for an assignment is a per-cell property, not a per-run property.

**Options:**

**Option A — add `input_feature_set` to `CellToClusterMapping` directly.** Each mapping record carries the featureset used to produce it. Simple, directly queryable, and requires no new classes. Slightly redundant when most cells in a run share the same featureset, but that's a minor cost.

**Option B — introduce a sub-run or cell-group concept on `AlgorithmRun`.** The run is parameterized by (cell population × featureset) pairs, and each `CellToClusterMapping` points to the (run, subgroup) that produced it. More structured, but adds complexity that only pays off if run parameters need to be queried as a first-class object.

**Preferred direction:** Option A unless there is a clear need to query full run parameterization, in which case Option B.

---

## 8. Typo: `heirachy` → `hierarchy` throughout clustering schema

**Problem:** `clustering_schema.yaml` misspells "hierarchy" in multiple places:
- Slot: `heirachy_category` on `Cluster`
- Class: `HierachyCategory` (should be `HierarchyCategory`)
- Description text in `HierachyCategory.level`

These propagate into generated `models.py` field names and delta lake column names (e.g., the `heirachy_category` column in the `cluster` table).

**Action:** Rename all instances to the correct spelling in the schema YAML, regenerate `models.py`, and rename the `heirachy_category` column in existing delta tables. This is a breaking change — best done now while there are no external consumers.

---

## ~~9. `Cluster` table has no link to its source taxonomy version or dataset~~ [CLOSED — merged into #3]

**Resolution:** The taxonomy versioning concern is now part of issue 3, which covers both taxonomy identification and versioning in a single issue.

---

## 10. `ProjectionMeasurementMatrix` needs a `laterality` field

**Problem:** Axon projection data splits into ipsilateral and contralateral measurements, but the schema has no field for this. The WNM ingestion (yy14) works around it by storing two separate matrices (`wnm_exc_proj_ipsi` / `wnm_exc_proj_contra`) with laterality encoded in the `id` string — not queryable.

**Action:** Add a `Laterality` enum to `base_schema.yaml` with values `IPSILATERAL`, `CONTRALATERAL`, `BILATERAL`, `UNKNOWN`. Add a `laterality` slot to `ProjectionMeasurementMatrix` in `projection_schema.yaml`. This is a natural property of any projection measurement and will apply to future datasets (anterograde tracers, rabies, etc.).

---

## 11. No schema class for experimental sample metadata (cre line, transgenic reporter)

**Problem:** `FullMorphMetaData_Master.csv` for the WNM dataset contains `cre_line` values like `"Fezf2-CreER;Ai166_439168-191807"` encoding the transgenic mouse line, reporter, and animal ID. No schema class covers this. `CellGeneData` / `BarcodingExperimentMetadata` is for expression matrices and is semantically incorrect. `SingleCellReconstruction` covers morphology provenance but not genetics. This metadata is currently skipped in yy14 with no schema home.

**Action:** Add a `SampleMetadata` class (or extend `DataItem` with optional sample annotation slots) covering at minimum: `cre_line`, `animal_id`, `reporter_line`. These fields are common across Allen Institute datasets and will recur. Alternatively, a generic key-value `Annotation` class on `DataItem` would handle this and other unstructured metadata.

---

## 12. `CellFeatureMatrix` pointer table is never written — wide-form data is unlinked from schema [ETL TODO, not a schema fix]

> **Note:** This is not a schema issue — the `CellFeatureMatrix` class already exists and is correctly defined. The problem is that ETL notebooks don't write it. This belongs in the ETL tooling backlog.

**Problem:** No `cellfeaturematrix` delta table exists in the combined datasets. All `cellfeatures/*` tables are orphaned from the schema — a consumer has no schema-level way to discover where feature data lives without knowing the `cellfeatures/*` path convention.

**Open design question:** `cellfeatures/exc_morph_features` contains rows for two `project_id` values (`visp_exc_patchseq` and `visp_exc_wnm`) in the same physical table. Should there be one `CellFeatureMatrix` row or two rows pointing to the same `parquet_path`?

**Action:** Add a helper function to the toolkit that auto-writes a `CellFeatureMatrix` row whenever a `cellfeatures/*` table is written. Backfill existing tables. Resolve the shared-path design question first.

---

## 13. Dataset-level projection coverage flag per brain region [NEW]

**Problem:** There is no schema-level way to ask "which CCF brain regions does dataset X have projection data in?" A consumer must load the full `ProjectionMeasurementMatrix` (cells × regions), check which columns have any non-zero values, and derive the answer themselves. This is a common query for cross-dataset comparison and should be precomputed.

**Proposed solution:** A toolkit function reads a `ProjectionMeasurementMatrix`, collapses across cells (any value > 0 per region column), and produces a 1×regions binary vector indicating "this dataset has projection data in region X." The result is written to a new schema class or field.

**Design options (to discuss):**
- Add a `region_coverage` field (list of bool, parallel to `region_index`) directly on `ProjectionMeasurementMatrix` — simple, co-located with the data
- Create a standalone `ProjectionCoverage` class referencing the matrix — more flexible, but adds indirection
- Add a `has_projection_data` flag to `BrainRegionAssociation` — per-dataset-per-region, queryable, but more rows

**Action:** Decide on the schema representation. Implement the toolkit function that computes coverage from existing projection data and writes it to the chosen schema target.
