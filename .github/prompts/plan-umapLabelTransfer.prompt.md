# Plan: UMAP Label Transfer patchseq → minnie in yy07

Add new cells to `code/yy07_EM_to_patchseq_types.ipynb`, after the existing content, implementing the full UMAP-based label transfer pipeline.

---

## Phase 1 — Data Loading

1. New imports cell: `pandas`, `numpy`, `sklearn.preprocessing.StandardScaler`, `sklearn.neighbors.NearestNeighbors`, `umap`, `matplotlib.pyplot`, `scipy.stats.mode`
2. Load **patchseq features**: `pl.read_delta(DATA_ROOT + '/cellfeatures/exc_morph_features')` filtered by `project_id == 'visp_exc_patchseq'` and `feature_set_id == 'exc_visp_morph_features'`
3. Load **patchseq labels**: `pl.read_delta(DATA_ROOT + '/clustermembership')` filtered by `project_id == 'visp_exc_patchseq'`; join onto features via `features.id == clustermembership.item`; the `cluster` column already contains descriptive MET-type names
4. Load **minnie features**: `pl.read_delta(DATA_ROOT + '/cellfeatures/minnie_exc_skel_keys')` filtered by `project_id == 'minnie65'` and `feature_set_id == 'minnie_exc_skel_keys'`

---

## Phase 2 — Feature Harmonization

5. Identify metadata columns to exclude: `['id', 'project_id', 'feature_set_id']`
6. Compute `shared_features` dynamically: use `get_list_differences` from `code/utils.py` with `return_lists=True`; print dropped features and shared feature count
7. Subset both DataFrames to shared features; drop NaN rows and report counts

---

## Phase 3 — Scaling

8. Fit `StandardScaler` on patchseq shared features; transform both patchseq and minnie

---

## Phase 4 — UMAP Projection

9. Fit UMAP on scaled patchseq (`random_state=42`); call `.transform()` on scaled minnie to project into the same 2D embedding space

---

## Phase 5 — KNN Label Transfer

10. Fit `NearestNeighbors(n_neighbors=3)` on `patchseq_embedding`; query with `minnie_embedding`; majority vote of 3 nearest neighbors → `minnie_predicted_labels`

---

## Phase 6 — Visualization (3 panels, `s=1.5`)

11. Build shared color dict: one `tab20` color per unique cluster label across both datasets
12. **Left**: both datasets colored by dataset identity — patchseq in one color, minnie in another (e.g. tab10 blue/orange); shows spatial overlap of the two populations
13. **Middle**: patchseq only, colored by true cluster label
14. **Right**: minnie only, colored by predicted cluster label
15. Single shared legend, "UMAP 1" / "UMAP 2" axis labels, `tight_layout`

---

## Relevant Files

- `code/yy07_EM_to_patchseq_types.ipynb` — all new cells appended after existing cell 13
- `code/utils.py` — `get_list_differences(..., return_lists=True)` for feature harmonization
- `DATA_ROOT = '/scratch/combined_datasets'` — already defined in notebook cell 2

### Delta table paths

| Dataset | Path |
|---|---|
| Patchseq excitatory features | `{DATA_ROOT}/cellfeatures/exc_morph_features` |
| Minnie excitatory features | `{DATA_ROOT}/cellfeatures/minnie_exc_skel_keys` |
| Cluster labels | `{DATA_ROOT}/clustermembership` → filter `project_id == 'visp_exc_patchseq'` |

---

## Verification Checkpoints

1. Print cell counts before/after NaN drop for each dataset
2. Print shared feature count vs. dropped feature count
3. Print first 5 rows of joined patchseq (features + label) to confirm join worked
4. Print `value_counts` of true patchseq labels and predicted minnie labels
5. Visual check: patchseq and minnie should partially overlap in UMAP space

---

## Decisions

- `cluster` column in `clustermembership` already contains descriptive label strings — no extra join to the cluster table needed
- Filter `clustermembership` by `project_id == 'visp_exc_patchseq'` to recover patchseq cells' MET-type assignments
- KNN: `n_neighbors=3`, majority vote
- Scaler: fit on patchseq, transform both
- UMAP: fit on patchseq, `.transform()` on minnie; `random_state=42`
- Colors: `tab20`

---

## Resolved Decisions

1. **Hierarchical labels**: No deduplication needed — `clustermembership` does not have multiple rows per cell for `project_id == 'visp_exc_patchseq'`.
2. **NaN handling**: Drop rows with any NaN in shared features; report count of dropped rows.
3. **Left panel coloring**: Both datasets colored by dataset identity (patchseq vs. minnie), not by cluster.
