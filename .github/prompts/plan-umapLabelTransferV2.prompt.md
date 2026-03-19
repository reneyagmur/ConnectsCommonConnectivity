# Plan: UMAPLabelTransfer Class + yy08 Demo Notebook

## Context
Refactor `yy07_EM_to_patchseq_types.ipynb` and `yy07_EM_to_patchseq_types-Copy1.ipynb` (EXC vs INH variants of the same pipeline) into a reusable class. Then generate a demo notebook yy08.

## Confirmed decisions
- "quadrant" → `quantile` (QuantileTransformer)
- h5ad: separate files for patchseq and minnie
- New file: `code/umap_label_transfer.py`
- yy08: 4 compact cells (one per run), ~8-10 lines each

---

## Phase A — Create `code/umap_label_transfer.py`

### Class: `UMAPLabelTransfer`

**Constructor `__init__(data_root, cell_type='exc', **overrides)`**
- `cell_type` in `{'exc', 'inh'}` auto-fills path/filter defaults
- Keyword overrides accepted for every individual path/filter param
- Sets `self.data_root`, `self.cell_type`, and all resolved path/filter attrs

EXC defaults:
- `ps_features_path`: `cellfeatures/exc_morph_features`
- `ps_project_id`: `visp_exc_patchseq`
- `ps_feature_set_id`: `exc_visp_morph_features`
- `mn_features_path`: `cellfeatures/minnie_exc_skel_keys`
- `mn_project_id`: `minnie65`
- `mn_feature_set_id`: `minnie_exc_skel_keys`
- `clustermembership_project_id`: `visp_exc_patchseq`

INH defaults:
- `ps_features_path`: `cellfeatures/inh_morph_features`
- `ps_project_id`: `visp_inh_patchseq`
- `ps_feature_set_id`: `inh_visp_morph_features`
- `mn_features_path`: `cellfeatures/minnie_inh_skel_keys`
- `mn_project_id`: `minnie65`
- `mn_feature_set_id`: `minnie_inh_skel_keys`
- `clustermembership_project_id`: `visp_inh_patchseq`

---

### Methods (all return `self` for chaining)

**1. `load_patchseq_features()`** → yy07 Cell 3
- `pl.read_delta(ps_features_path)` filtered by `ps_project_id` + `ps_feature_set_id`
- Sets `self._df_ps_feat`

**2. `load_patchseq_labels()`** → yy07 Cells 4–6
- Load `clustermembership`, filter by `clustermembership_project_id`
- Load `cluster` table, filter to `visp_met_types` project
- Per-cell keep deepest label: sort by `level` desc → `group_by('item').first()`
- Join labels onto features → sets `self._df_ps`

**3. `load_minnie_features()`** → yy07 Cell 7
- `pl.read_delta(mn_features_path)` filtered by `mn_project_id` + `mn_feature_set_id`
- Sets `self._df_mn`

**4. `load_data()`** — convenience wrapper calling 1 + 2 + 3 in sequence

**5. `harmonize_features()`** → yy07 Cells 8–9
- `META_COLS = {'id', 'project_id', 'feature_set_id', 'cluster'}`
- Use `get_list_differences(return_lists=True)` to compute `shared_features`; print dropped/shared counts
- Subset both to shared features, convert to pandas
- Drop NaN rows, report before/after counts
- Sets `self._df_ps_pd`, `self._df_mn_pd`, `self._shared_features`

**6. `save_harmonized_h5ad(output_dir)`** — NEW — call after `harmonize_features`, before `scale`
- Requires `self._df_ps_pd`, `self._df_mn_pd`, `self._shared_features`
- Patchseq h5ad: `X` = feature matrix, `obs` = {id, cluster}, `var` = shared_features
- Minnie h5ad: `X` = feature matrix, `obs` = {id}, `var` = shared_features
- Saves:
  - `{output_dir}/{cell_type}_patchseq_harmonized.h5ad`
  - `{output_dir}/{cell_type}_minnie_harmonized.h5ad`

**7. `scale(method='standard')`** → yy07 Cell 11
- `method` ∈ `{'standard', 'robust', 'quantile'}`
  - `'standard'` → `StandardScaler()`
  - `'robust'` → `RobustScaler()`
  - `'quantile'` → `QuantileTransformer(output_distribution='normal', n_quantiles=1000)`
- Fit on patchseq shared features, transform both datasets
- Sets `self._X_ps`, `self._X_mn`, `self._scaler`, `self.scaling_method`

**8. `plot_alignment_diagnostics(top_n=5)`** → yy07 Cells 12–14
- Compute per-feature `delta_mean` and `std_ratio` before/after scaling
- Panel 1: bar chart of all features (before vs. after)
- Panel 2: overlaid histograms for best/worst `top_n` aligned features
- Sets `self._alignment_df`

**9. `fit_umap(mode='unsupervised', **umap_kwargs)`** → yy07 Cell 15 / raw Cell 16
- `mode` ∈ `{'unsupervised', 'supervised'}`
  - `'unsupervised'`: `UMAP(n_components=2, random_state=42, init='random')`; fit on `X_ps`, `.transform(X_mn)`
  - `'supervised'`: `LabelEncoder` → `UMAP(init='spectral', n_jobs=1)` fit with `y=ps_labels_enc`; `.transform(X_mn)`
- Sets `self._ps_emb`, `self._mn_emb`, `self._reducer`, `self.umap_mode`

**10. `transfer_labels(k=3)`** → yy07 Cell 16
- `NearestNeighbors(n_neighbors=k).fit(ps_emb)`, `kneighbors(mn_emb)`
- `Counter` majority vote per minnie cell
- Sets `self._mn_predicted`, `self._ps_labels`

**11. `plot_umap()`** → yy07 Cell 17
- 3-panel figure:
  1. Both datasets, coloured by dataset identity (patchseq vs. minnie65)
  2. Patchseq only, coloured by true cluster label
  3. Minnie only, coloured by predicted cluster label
- Shared tab20 cluster colour dict across panels
- Title includes `cell_type` and `umap_mode`

**12. `run(scaling_method='standard', umap_mode='unsupervised', h5ad_output_dir=None, k=3, plot_diagnostics=True)`**
- Full pipeline convenience method:
  `load_data` → `harmonize_features` → [`save_harmonized_h5ad` if `h5ad_output_dir`] → `scale` → [`plot_alignment_diagnostics` if `plot_diagnostics`] → `fit_umap` → `transfer_labels` → `plot_umap`

---

## Phase B — Create `code/yy08demo_umap_label_transfer.ipynb`

| Cell | Content |
|------|---------|
| 0 | Setup: imports + `DATA_ROOT = '/scratch/combined_datasets'` |
| 1 | EXC — unsupervised UMAP |
| 2 | EXC — supervised UMAP |
| 3 | INH — unsupervised UMAP |
| 4 | INH — supervised UMAP |

Each of cells 1–4 is compact (~8–10 lines): instantiate → `load_data()` → `harmonize_features()` → `scale()` → `fit_umap(mode)` → `transfer_labels()` → `plot_umap()`.

The optional `save_harmonized_h5ad(output_dir)` step is shown commented-in between `harmonize_features()` and `scale()` in each cell.

---

## Files to create

| File | Action |
|------|--------|
| `code/umap_label_transfer.py` | CREATE |
| `code/yy08demo_umap_label_transfer.ipynb` | CREATE |

## Files untouched

| File | Reason |
|------|--------|
| `code/utils.py` | Imported as-is (`get_list_differences`) |
| `code/yy07_EM_to_patchseq_types.ipynb` | Reference only |
| `code/yy07_EM_to_patchseq_types-Copy1.ipynb` | Reference only |

## Dependencies

| Package | Usage |
|---------|-------|
| `polars` | Delta Lake reads |
| `pandas`, `numpy` | Feature manipulation |
| `sklearn` | StandardScaler, RobustScaler, QuantileTransformer, NearestNeighbors, LabelEncoder |
| `umap-learn` | UMAP fitting |
| `anndata` | h5ad serialisation |
| `matplotlib` | Alignment diagnostics, UMAP plots |
| `utils.get_list_differences` | Existing codebase helper |

---

## Verification checkpoints

1. `from umap_label_transfer import UMAPLabelTransfer` resolves without import errors
2. `UMAPLabelTransfer(DATA_ROOT, 'exc').load_data().harmonize_features()` prints expected shapes
3. `save_harmonized_h5ad` produces two `.h5ad` files with `adata.X.shape == (n_cells, n_shared_features)`
4. `scale(method='robust')` and `scale(method='quantile')` both run without error
5. `fit_umap('supervised')` produces non-degenerate embeddings
6. `plot_umap()` renders 3-panel figure with legend for both EXC and INH
7. All 4 yy08 cells execute top-to-bottom without errors
