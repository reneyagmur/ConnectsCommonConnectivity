# Schema Issues & Action Items

## 1. DataItem IDs are not globally unique across combined datasets

**Problem:** `id` is declared `identifier: true` in the base schema, but that only means unique within a single class context. When datasets are combined (e.g. in `yy05_combine_deltalakes_visp_microns`), rows are concatenated with no duplicate check. The `ProjectScoped` mixin adds `project_id` but `(project_id, id)` is never enforced as a composite key. EM segment IDs and patchseq specimen IDs could collide as bare strings.

**Action:** Define `(project_id, id)` as the effective composite unique key in the schema. Enforce it at write time in the combination script (dedup check or assert after concat). Consider prefixing IDs with their project namespace before writing to a shared store.

---

## 2. `ClusterMembership` and `CellToClusterMapping` model the same thing inconsistently

**Problem:** Both classes represent "this cell has been assigned to this cluster." The distinction — native membership vs. cross-taxonomy mapping — breaks down in practice, because all patchseq and WNM cells are being *assigned* to external taxonomies, never built them. `ClusterMembership` lacks `MappingSet` entirely, so assignments via it have no provenance (no method name, no source/target dataset). In `patchseq_type_mapping.ipynb`, MET-type assignments for `visp_inh_patchseq` and `visp_exc_patchseq` use `ClusterMembership`, while the equivalent WNM MET-type assignment uses `CellToClusterMapping` — the author flagged this inconsistency in a comment in that notebook.

**Action:** Deprecate `ClusterMembership`. Migrate all existing uses to `CellToClusterMapping` with a required `MappingSet`. The immediate cases are the patchseq MET-type assignments in `patchseq_type_mapping.ipynb`.

---

## 3. Cell→cluster associations don't record which taxonomy the cluster belongs to

**Problem:** `ClusterMembership.cluster` is typed as `Cluster`, but cluster labels like `"Glutamatergic"` or `"L6b"` appear in multiple taxonomies (`minnie65`, `visp_met_types`, `tasic_2018_visp_scrnaseq`). The `project_id` on the association row refers to the *cell's* project, not the cluster's taxonomy. `CellToClusterMapping` partially solves this via `MappingSet.target_dataset`, but only if `MappingSet` is present and populated. This is already noted as a problem in `yy05_combine_deltalakes_visp_microns.ipynb`.

**Action:** Add a required `cluster_project_id` (or `target_hierarchy`) field to any cell→cluster association class, explicitly separate from the cell's own `project_id`.

---

## 4. `CellFeatureDefinition` IDs are not namespaced and will collide across featuresets

**Problem:** A feature named `total_length` in `minnie_exc_skel_keys` and `total_length` in a patchseq featureset have the same `id` in the schema. The current workaround is Delta Lake sub-path partitioning (`cellfeaturedefinition/minnie_exc_skel_keys/`), but nothing in the schema prevents collisions in a combined flat table.

**Action:** Namespace feature definition IDs by featureset at the schema level (e.g. `minnie_exc_skel_keys:total_length`), or add `feature_set_id` as a required field on `CellFeatureDefinition` and make `(feature_set_id, id)` the composite key.

---

## 5. `AlgorithmRun` and `ClusterHierarchy` are never written, and `AlgorithmRun` has no link to a featureset

**Problem:** These classes exist in `clustering_schema.yaml` and are intended to capture provenance — which algorithm, on which input, produced a given taxonomy. In practice, no `AlgorithmRun` or `ClusterHierarchy` records are ever written; `Cluster` nodes are written directly, partitioned only by `project_id`. Additionally, `AlgorithmRun.input_dataset` points to a `DataSet`, but the same dataset can have multiple featuresets — so it is impossible to record which featureset was the actual input to the clustering run.

**Action:** Add an `input_feature_set` slot (→ `CellFeatureSet`) to `AlgorithmRun`. Then write `AlgorithmRun` + `ClusterHierarchy` records when ingesting each taxonomy (e.g. in `process_patchseq_taxonomy_info.ipynb`). If that is out of scope for now, remove these classes until they are ready to be used.

---

## 6. No schema mechanism for a combined/derived featureset

**Problem:** The EXC and INH skeleton keys feature sets for Minnie65 differ from VISp sets (documented in `yy06_combine_EM_skel-keys_feats.ipynb`) and were therefore written as separate featuresets. The intention to eventually produce a unified combined featureset across EM and patchseq is noted in that notebook, but there is no schema concept to represent a featureset that is derived from or is the intersection/union of others, including feature rename or alignment mappings.

**Action:** Add a featureset composition concept — a `CellFeatureSet` that declares `derived_from` (list of source featuresets) and an optional feature alignment mapping. This is the schema prerequisite for any future combined morphology featureset.

---

## 7. Cells within the same dataset may use different featuresets (or feature subsets) when being mapped to the same clusterset

**Problem:** `AlgorithmRun.input_feature_set` (proposed in item 5) assumes one featureset per run, but this doesn't hold when cells in the same dataset have heterogeneous features. The concrete case: Minnie65 EXC cells use `minnie_exc_skel_keys` and INH cells use `minnie_inh_skel_keys`, but both are assigned to the same taxonomy. If patchseq EXC and INH datasets were ever merged into one, the same problem would apply there too. The featureset used for an assignment is a per-cell property, not a per-run property.

**Options:**

**Option A — add `input_feature_set` to `CellToClusterMapping` directly.** Each mapping record carries the featureset used to produce it. Simple, directly queryable, and requires no new classes. Slightly redundant when most cells in a run share the same featureset, but that's a minor cost.

**Option B — introduce a sub-run or cell-group concept on `AlgorithmRun`.** The run is parameterized by (cell population × featureset) pairs, and each `CellToClusterMapping` points to the (run, subgroup) that produced it. More structured, but adds complexity that only pays off if run parameters need to be queried as a first-class object.

**Preferred direction:** Option A unless there is a clear need to query full run parameterization, in which case Option B.

---

## 8. Typo: `heirachy` / `heirarchy` throughout clustering schema

**Problem:** `clustering_schema.yaml` consistently misspells "hierarchy" as `heirarchy` / `heirachy` — appearing in slot names (`heirachy_category`), class names (`HierachyCategory`), and field names (`produced_hierarchies` is correct but `ClusterHierarchy` vs `HierachyCategory` are inconsistent). This propagates into generated `models.py` and all delta lake column names (`heirachy_category` column in `cluster` table).

**Action:** Correct all instances to `hierarchy` in the schema YAML, regenerate `models.py`, and migrate the `heirachy_category` column in any existing delta tables. This is a breaking rename — coordinate with any downstream consumers reading that column by name.

---

## 9. `Cluster` table has no link to its source taxonomy version or dataset

**Problem:** `Cluster` rows are scoped only by `project_id` (e.g. `"visp_met_types"`, `"minnie65"`). This is not descriptive enough: the same project can have multiple clustering runs or taxonomy versions over time, and there is no field to record which version of a taxonomy (e.g. CCN20230722, v1.0) a cluster belongs to. A consumer cannot distinguish clusters from different releases of the same taxonomy without external knowledge.

**Action:** Add a `taxonomy_version` (or `algorithm_run_id`) slot to `Cluster`, making `(project_id, taxonomy_version, id)` the effective unique key. At minimum, add an optional `description` or `version` string field directly on `Cluster`. Long-term, this ties back to Issue 5 (`AlgorithmRun` / `ClusterHierarchy` provenance).

---

## 10. `ProjectionMeasurementMatrix` has no `laterality` field (ipsi vs contra)

**Problem:** Axon projection data naturally splits into ipsilateral and contralateral measurements. The current schema has no field to encode this — only `measurement_type` (e.g. `NUMBER_OF_TIPS`) and `modality`. The workaround used in the WNM ingestion (yy14) is to store two separate `ProjectionMeasurementMatrix` objects (`wnm_exc_proj_ipsi` / `wnm_exc_proj_contra`) and encode laterality in the `id` string. This is informal and not queryable.

**Options:**

**Option A — add a `laterality` enum field** (`IPSILATERAL`, `CONTRALATERAL`, `BILATERAL`, `UNKNOWN`) to `ProjectionMeasurementMatrix`. Clean, queryable, schema-enforced.

**Option B — keep two separate matrices** (current workaround) and document the naming convention. Simple but relies on ID string parsing.

**Preferred direction:** Option A. A `laterality` enum is a natural property of any projection measurement and will apply to future datasets (e.g. anterograde tracer injections) as well.

---

## 11. No schema class for experimental sample metadata (cre line, transgenic reporter)

**Problem:** `FullMorphMetaData_Master.csv` for the WNM dataset contains `cre_line` values like `"Fezf2-CreER;Ai166_439168-191807"` encoding the transgenic mouse line, reporter, and animal ID. No schema class covers this. `CellGeneData` / `BarcodingExperimentMetadata` is for expression matrices and is semantically incorrect. `SingleCellReconstruction` covers morphology provenance but not genetics. This metadata is currently skipped in yy14 with no schema home.

**Action:** Add a `SampleMetadata` class (or extend `DataItem` with optional sample annotation slots) covering at minimum: `cre_line`, `animal_id`, `reporter_line`. These fields are common across Allen Institute datasets and will recur. Alternatively, a generic key-value `Annotation` class on `DataItem` would handle this and other unstructured metadata.

---

## 12. `CellFeatureMatrix` pointer table is never written — wide-form data is unlinked from schema

**Problem:** `CellFeatureMatrix` is the schema class that links a `CellFeatureSet` (metadata) to the physical wide-form data table via `parquet_path` and `cell_index_column`. Without it, a consumer reading the schema has no way to discover where the actual feature numbers live — the `cellfeatures/*` path convention is implicit and undocumented at the schema level. Currently, no `cellfeaturematrix` delta table exists in the combined datasets; all `cellfeatures/*` tables are orphaned from the schema perspective.

**Open design question:** `cellfeatures/exc_morph_features` contains rows for two `project_id` values (`visp_exc_patchseq` and `visp_exc_wnm`) in the same physical table. Should there be one `CellFeatureMatrix` row (ambiguous `project_id`) or two rows pointing to the same `parquet_path`?

**Action:** Create a `cellfeaturematrix` delta table. Backfill one `CellFeatureMatrix` row per existing `cellfeatures/*` table. Add a `CellFeatureMatrix` write step to every future notebook that writes a `cellfeatures/*` table. Resolve the shared-path design question before backfilling.
