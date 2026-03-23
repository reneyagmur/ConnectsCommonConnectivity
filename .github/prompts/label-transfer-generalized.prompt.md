---
description: "Create a generalized LabelTransfer class for UMAP-based label transfer between two user-defined Delta Lake feature datasets"
name: "Generalized Label Transfer Class"
agent: "agent"
---

Create a new file `code/label_transfer.py` with a `LabelTransfer` class that generalises `UMAPLabelTransfer` in [code/umap_label_transfer.py](../../code/umap_label_transfer.py).

## Requirements

- Two datasets (source = labeled, target = unlabeled) provided via Delta Lake paths + filter kwargs — no hardcoded exc/inh presets
- Source labels loaded from `clustermembership` + `cluster` Delta Lake tables; `clustermembership` is always filtered by `source_project_id` (no separate param needed); `source_label_taxonomy_project_id` is configurable and defaults to `"visp_met_types"`
- Column names always `'id'` and `'cluster'`
- Transfer method is pluggable: constructor takes `method: Literal["umap"] = "umap"`; raise `NotImplementedError` for anything else
- `run()` returns a `pd.DataFrame({"id": ..., "predicted_label": ...})` — not `self`
- Keep diagnostics and UMAP plot methods (`plot_alignment_diagnostics`, `plot_umap`)
- Keep `UMAPLabelTransfer` in `umap_label_transfer.py` unchanged

## Constructor signature

```python
LabelTransfer(
    data_root: str,
    source_features_subpath: str,
    source_project_id: str,
    source_feature_set_id: str,
    target_features_subpath: str,
    target_project_id: str,
    target_feature_set_id: str,
    source_label_taxonomy_project_id: str = "visp_met_types",
    method: Literal["umap"] = "umap",
)
```

`clustermembership` is always filtered by `source_project_id` — no separate parameter.

## Phase ordering

`load_data()` → `harmonize_features()` → optionally `save_harmonized_h5ad()` → `scale()` → `fit()` → `transfer_labels()` → `predict()` / `plot_umap()`

## Key design points

1. **DRY loading**: single private `_load_features(subpath, project_id, feature_set_id) -> pl.DataFrame` used for both source and target — removes the duplication of `load_patchseq_features` / `load_minnie_features`
2. **Generalised label loading**: `_load_labels()` filters `clustermembership` by `source_project_id` and the `cluster` table by `source_label_taxonomy_project_id`; keeps deepest-level (highest `level`) label per cell; extracts `_cluster_colors` from `hex_color` column if present
3. **Method dispatch**: `fit(mode='unsupervised', **kwargs)` delegates to `_fit_umap(mode, **kwargs)` for `method='umap'`; raises `NotImplementedError` for any other value — extensibility hook for future methods
4. **Output**: `predict() -> pd.DataFrame` with columns `['id', 'predicted_label']` where `id` values come from `_df_target_pd["id"]`; `run()` calls `predict()` and returns that DataFrame

## Internal state naming

Use `_df_source` / `_df_target` (and `_df_source_pd` / `_df_target_pd`, `_X_source` / `_X_target`, `_source_emb` / `_target_emb`, `_source_labels` / `_target_predicted`) instead of the old `_df_ps` / `_df_mn` naming.

## Visualisation

`plot_umap()` — same 3-panel figure as `UMAPLabelTransfer.plot_umap()`, with generic "source" / "target" labels instead of "patchseq" / "minnie65" in titles.

`plot_alignment_diagnostics(top_n=5)` — identical logic to existing class.

## Imports and utilities

Use the same imports as [code/umap_label_transfer.py](../../code/umap_label_transfer.py). Import `get_list_differences` from [code/utils.py](../../code/utils.py) unchanged for use in `harmonize_features()`.

---

## Demo notebook: `code/yy08_label_transfer_demo.ipynb`

Also create a demo notebook `code/yy08_label_transfer_demo.ipynb` that demonstrates `LabelTransfer` end-to-end. Follow the same style as code/yy07:

- Use `%load_ext autoreload` / `%autoreload 2`
- Use `DATA_ROOT = "/data/microns1412/"` as the data root variable
- Use markdown section headers to separate each phase
- Use the same Delta Lake paths already known from `yy07*`:

| Variable | Value |
|---|---|
| `DATA_ROOT` | `/data/microns1412/` |
| EXC source features subpath | `cellfeatures/exc_morph_features` |
| EXC source project_id | `visp_exc_patchseq` |
| EXC source feature_set_id | `exc_visp_morph_features` |
| EXC target features subpath | `cellfeatures/minnie_exc_skel_keys` |
| EXC target project_id | `minnie65` |
| EXC target feature_set_id | `minnie_exc_skel_keys` |
| INH source features subpath | `cellfeatures/inh_morph_features` |
| INH source project_id | `visp_inh_patchseq` |
| INH source feature_set_id | `inh_visp_morph_features` |
| INH target features subpath | `cellfeatures/minnie_inh_skel_keys` |
| INH target project_id | `minnie65` |
| INH target feature_set_id | `minnie_inh_skel_keys` |

`source_label_taxonomy_project_id` defaults to `"visp_met_types"` for both — omit unless overriding.

### Notebook structure

1. **Imports** — `import sys; sys.path.insert(0, '.')`, autoreload, then `from label_transfer import LabelTransfer`
2. **Config** — `DATA_ROOT` variable cell
3. **Section: EXC label transfer**
   - Instantiate `LabelTransfer` for EXC using the values from the table above (`source_label_taxonomy_project_id` can be omitted since it defaults to `"visp_met_types"`)
   - Call `run()` with `scaling_method='standard'`, `umap_mode='supervised'`, `plot_diagnostics=True`
   - Store the returned DataFrame in `exc_result` and display it with `.head()`
4. **Section: INH label transfer**
   - Same as above for INH using the INH values from the table; store result in `inh_result`
5. **Section: Combined results**
   - Concatenate `exc_result` and `inh_result` into `all_results`
   - Show value counts of `predicted_label` 
   - Display the final DataFrame
