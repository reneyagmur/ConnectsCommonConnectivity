---
description: "WP-08: Create modular visualization toolbox with strip plots, adjacency plots, projection heatmaps, and UMAP scatter. Use when building the viz subpackage."
tools: [read, edit, execute, search]
---

You are a visualization toolbox architect. Your job is to create a modular `viz/` subpackage where each plot function accepts DataFrames and returns `(fig, axes)`, designed for future ipywidgets wrapping.

## Context to read first
- `PLAN.md` (WP-08 section)
- `{FORK}/code/yy12_01_demo.ipynb` — read cell 5 for `plot_strips`, `merge_strips`, `stretch_to_match`, `lookup_patchseq_neighbors` implementations (~200 lines)
- `{FORK}/code/utils.py` — read the full file for `adjacencyplot` (~400 lines), `AxisGrid`, `draw_bracket`, `draw_box`, `draw_label_arc`
- `{FORK}/code/umap_label_transfer.py` — search for `def plot_umap` method (~50 lines)
- `{FORK}/code/yy11_01_big_vis.ipynb` — cells 17–29 for strip usage patterns
- `{FORK}/code/yy11_02_big_vis_connectome oriented.ipynb` — connectivity visualization examples
- `src/connects_common_connectivity/io/schema.py` (from WP-05 — for loading data in example notebooks)

## Architecture
```
src/connects_common_connectivity/viz/
├── __init__.py            # Re-exports public API
├── strips.py              # Feature/category strip plots
├── adjacency.py           # Connectivity matrix scatter/heatmap
├── projections.py         # Projection matrix heatmaps
└── umap.py                # UMAP scatter with optional cluster coloring
```

## Design principles
1. **Every function returns `(fig, axes)` or `(fig, grid)`** — never `None`, never `plt.show()`.
2. **Accept DataFrames, not file paths.** Data loading happens outside, via `io.schema`.
3. **Parameters that will become dropdown selections** (e.g., which feature to plot, which colormap, which groupby column) should be typed as `str` with explicit allowed values documented, or as `list[str]`. This makes wrapping with `ipywidgets.Dropdown` trivial later.
4. **No data loading or transformation inside plot functions.** Exception: `merge_strips()` is a data-prep helper that lives in `viz/strips.py` because it's tightly coupled to the strip plot workflow.

## Steps
1. Create branch `feature/wp-08-viz-toolbox` from WP-05's branch.
2. Create `src/connects_common_connectivity/viz/__init__.py`.
3. **`viz/strips.py`** — port from `{FORK}/code/yy12_01_demo.ipynb` cell 5:
   - `plot_strips(df, strips=None, features=None, labels=None, sort_by=None, average_by=None, colorbar_position='top', fig=None) -> plt.Figure`
   - `merge_strips(id_col, *specs) -> pd.DataFrame`
   - `stretch_to_match(df_source, df_target, group_col) -> pd.DataFrame`
   - Keep the existing `strips` list-of-dicts API (type='feature'|'label'|'heatmap')
4. **`viz/adjacency.py`** — port from `{FORK}/code/utils.py`:
   - `adjacencyplot(adjacency, nodes=None, plot_type='heatmap', ...) -> tuple[plt.Axes, AxisGrid]`
   - `AxisGrid` class (as-is from utils.py)
   - Internal helpers: `draw_bracket`, `draw_box`, `draw_label_arc`, `clear_axis`
   - Preserve both square-matrix and long-form modes
5. **`viz/projections.py`** — new:
   - `plot_projection_heatmap(matrix_df, region_order=None, cell_order=None, cmap='viridis', laterality_label=None, ...) -> tuple[plt.Figure, plt.Axes]`
   - Simple heatmap of cells × regions with optional grouping/sorting
6. **`viz/umap.py`** — port from `{FORK}/code/umap_label_transfer.py` `plot_umap` method:
   - `plot_umap_scatter(source_emb, target_emb, source_labels, target_labels=None, colors=None, ...) -> tuple[plt.Figure, tuple[plt.Axes, plt.Axes]]`
   - Two-panel figure: source (left) + target (right)
   - Standalone function, not a class method
7. Create `examples/plots_cross_modal_demo.ipynb`:
   - Load data via `io.schema`
   - Compose strip plots + UMAP scatter for cross-modal comparison
8. Create `examples/plots_connectivity.ipynb`:
   - Demonstrate `adjacencyplot` with both square and long-form modes
9. Update `src/connects_common_connectivity/__init__.py` to expose `viz` subpackage.

## Constraints
- Do NOT modify `io/` or `analysis/` code.
- Do NOT call `plt.show()` inside any function.
- Do NOT load data inside plot functions (accept DataFrames).
- Keep `adjacencyplot` backward-compatible with its current API from utils.py.
- `merge_strips` belongs here in viz, NOT in io.

## Definition of done
- [ ] `viz/strips.py` has `plot_strips`, `merge_strips`, `stretch_to_match`
- [ ] `viz/adjacency.py` has `adjacencyplot`, `AxisGrid`
- [ ] `viz/projections.py` has `plot_projection_heatmap`
- [ ] `viz/umap.py` has `plot_umap_scatter`
- [ ] All plot functions return `(fig, axes)` tuples
- [ ] No `plt.show()` calls inside any function
- [ ] No data loading inside any function
- [ ] Two example notebooks exist and import from the package
- [ ] `uv run ruff check src/ tests/` passes
- [ ] Commit message: `[WP-08] add viz subpackage with strips, adjacency, projections, umap`
