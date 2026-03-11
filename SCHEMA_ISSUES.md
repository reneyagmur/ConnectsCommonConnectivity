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
