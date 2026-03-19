"""UMAP-based label transfer: patchseq (VISp) → minnie65.

Encapsulates the full 6-phase pipeline from yy07_EM_to_patchseq_types.ipynb
(EXC) and yy07_EM_to_patchseq_types-Copy1.ipynb (INH):

    Phase 1 — Load data
    Phase 2 — Feature harmonisation
    Phase 3 — Scaling  (standard | robust | quantile)
    Phase 4 — UMAP projection  (unsupervised | supervised)
    Phase 5 — KNN label transfer
    Phase 6 — Visualisation

Usage (quick):
    from umap_label_transfer import UMAPLabelTransfer

    lt = UMAPLabelTransfer(DATA_ROOT, cell_type='exc')
    lt.run(scaling_method='standard', umap_mode='unsupervised')

Usage (step-by-step with optional h5ad save):
    lt = UMAPLabelTransfer(DATA_ROOT, cell_type='inh')
    lt.load_data()
    lt.harmonize_features()
    lt.save_harmonized_h5ad('/path/to/output')   # optional, before scaling
    lt.scale(method='robust')
    lt.plot_alignment_diagnostics()
    lt.fit_umap(mode='supervised')
    lt.transfer_labels(k=3)
    lt.plot_umap()
"""

from __future__ import annotations

import os
from collections import Counter
from typing import Literal

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import polars as pl
import umap
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import (
    LabelEncoder,
    QuantileTransformer,
    RobustScaler,
    StandardScaler,
)

from utils import get_list_differences


# ---------------------------------------------------------------------------
# Per-cell-type configuration defaults
# ---------------------------------------------------------------------------

_DEFAULTS: dict[str, dict] = {
    "exc": dict(
        ps_features_subpath="cellfeatures/exc_morph_features",
        ps_project_id="visp_exc_patchseq",
        ps_feature_set_id="exc_visp_morph_features",
        mn_features_subpath="cellfeatures/minnie_exc_skel_keys",
        mn_project_id="minnie65",
        mn_feature_set_id="minnie_exc_skel_keys",
        clustermembership_project_id="visp_exc_patchseq",
    ),
    "inh": dict(
        ps_features_subpath="cellfeatures/inh_morph_features",
        ps_project_id="visp_inh_patchseq",
        ps_feature_set_id="inh_visp_morph_features",
        mn_features_subpath="cellfeatures/minnie_inh_skel_keys",
        mn_project_id="minnie65",
        mn_feature_set_id="minnie_inh_skel_keys",
        clustermembership_project_id="visp_inh_patchseq",
    ),
}

_META_COLS = {"id", "project_id", "feature_set_id", "cluster"}

ScalingMethod = Literal["standard", "robust", "quantile"]
UMAPMode = Literal["unsupervised", "supervised"]


class UMAPLabelTransfer:
    """UMAP-based label transfer from patchseq to minnie65 EM neurons.

    Parameters
    ----------
    data_root:
        Root path that contains all Delta Lake tables
        (e.g. ``'/scratch/combined_datasets'``).
    cell_type:
        Either ``'exc'`` (excitatory) or ``'inh'`` (inhibitory).  Drives all
        default path and filter values.
    **overrides:
        Override any individual path/filter default.  Accepted keys:
        ``ps_features_subpath``, ``ps_project_id``, ``ps_feature_set_id``,
        ``mn_features_subpath``, ``mn_project_id``, ``mn_feature_set_id``,
        ``clustermembership_project_id``.
    """

    def __init__(
        self,
        data_root: str,
        cell_type: Literal["exc", "inh"] = "exc",
        **overrides,
    ) -> None:
        if cell_type not in _DEFAULTS:
            raise ValueError(f"cell_type must be 'exc' or 'inh', got '{cell_type}'")

        self.data_root = data_root
        self.cell_type = cell_type

        cfg = {**_DEFAULTS[cell_type], **overrides}
        self.ps_features_subpath: str = cfg["ps_features_subpath"]
        self.ps_project_id: str = cfg["ps_project_id"]
        self.ps_feature_set_id: str = cfg["ps_feature_set_id"]
        self.mn_features_subpath: str = cfg["mn_features_subpath"]
        self.mn_project_id: str = cfg["mn_project_id"]
        self.mn_feature_set_id: str = cfg["mn_feature_set_id"]
        self.clustermembership_project_id: str = cfg["clustermembership_project_id"]

        # State populated by each phase
        self._df_ps_feat: pl.DataFrame | None = None
        self._df_ps: pl.DataFrame | None = None
        self._df_mn: pl.DataFrame | None = None
        self._df_ps_pd: pd.DataFrame | None = None
        self._df_mn_pd: pd.DataFrame | None = None
        self._shared_features: list[str] | None = None
        self._X_ps: np.ndarray | None = None
        self._X_mn: np.ndarray | None = None
        self._scaler = None
        self.scaling_method: str | None = None
        self._alignment_df: pd.DataFrame | None = None
        self._reducer = None
        self._ps_emb: np.ndarray | None = None
        self._mn_emb: np.ndarray | None = None
        self.umap_mode: str | None = None
        self._ps_labels: np.ndarray | None = None
        self._mn_predicted: np.ndarray | None = None

    # ------------------------------------------------------------------
    # Phase 1 — Data loading
    # ------------------------------------------------------------------

    def load_patchseq_features(self) -> "UMAPLabelTransfer":
        """Load patchseq morphology features from the Delta Lake table."""
        path = os.path.join(self.data_root, self.ps_features_subpath)
        df = pl.read_delta(path).filter(
            (pl.col("project_id") == self.ps_project_id)
            & (pl.col("feature_set_id") == self.ps_feature_set_id)
        )
        print(f"Patchseq features: {df.shape}")
        self._df_ps_feat = df
        return self

    def load_patchseq_labels(self) -> "UMAPLabelTransfer":
        """Load cluster labels and join them onto patchseq features.

        Strategy: load ``clustermembership`` + ``cluster`` tables, keep the
        deepest (highest ``level``) label per cell, then inner-join onto
        ``self._df_ps_feat``.
        """
        if self._df_ps_feat is None:
            raise RuntimeError("Call load_patchseq_features() first.")

        # --- clustermembership filtered to this cell type's patchseq project
        df_ps_labels_raw = pl.read_delta(
            os.path.join(self.data_root, "clustermembership")
        ).filter(pl.col("project_id") == self.clustermembership_project_id)

        # --- cluster table filtered to visp_met_types (shared taxonomy)
        df_clusters = pl.read_delta(os.path.join(self.data_root, "cluster"))
        df_clusters_met = df_clusters.filter(
            pl.col("project_id") == "visp_met_types"
        )

        # Per patchseq cell: keep deepest (most specific) cluster label
        df_ps_labels = (
            df_ps_labels_raw.select(["item", "cluster"])
            .join(
                df_clusters_met.select(["id", "level", "heirachy_category"]),
                left_on="cluster",
                right_on="id",
                how="left",
            )
            .sort("level", descending=True, nulls_last=True)
            .group_by("item")
            .first()
            .select(["item", "cluster", "level", "heirachy_category"])
        )

        print(
            f"Unique patchseq cells: {df_ps_labels['item'].n_unique()}, "
            f"unique labels: {df_ps_labels['cluster'].n_unique()}"
        )

        # Join onto features
        df_ps = self._df_ps_feat.join(
            df_ps_labels, left_on="id", right_on="item", how="inner"
        )
        print(f"Patchseq after label join: {df_ps.shape}")
        self._df_ps = df_ps
        return self

    def load_minnie_features(self) -> "UMAPLabelTransfer":
        """Load minnie65 skeleton-keys features from the Delta Lake table."""
        path = os.path.join(self.data_root, self.mn_features_subpath)
        df = pl.read_delta(path).filter(
            (pl.col("project_id") == self.mn_project_id)
            & (pl.col("feature_set_id") == self.mn_feature_set_id)
        )
        print(f"Minnie features: {df.shape}")
        self._df_mn = df
        return self

    def load_data(self) -> "UMAPLabelTransfer":
        """Convenience wrapper: load patchseq features + labels + minnie features."""
        self.load_patchseq_features()
        self.load_patchseq_labels()
        self.load_minnie_features()
        return self

    # ------------------------------------------------------------------
    # Phase 2 — Feature harmonisation
    # ------------------------------------------------------------------

    def harmonize_features(self) -> "UMAPLabelTransfer":
        """Identify shared features, subset both datasets, drop NaN rows."""
        if self._df_ps is None or self._df_mn is None:
            raise RuntimeError("Call load_data() first.")

        ps_feat_cols = [c for c in self._df_ps.columns if c not in _META_COLS]
        mn_feat_cols = [c for c in self._df_mn.columns if c not in _META_COLS]

        only_in_ps, only_in_mn = get_list_differences(
            ps_feat_cols, mn_feat_cols, return_lists=True, print_lists=False
        )
        shared = sorted(set(ps_feat_cols) & set(mn_feat_cols))

        print(f"Shared features:  {len(shared)}")
        print(f"Only in patchseq: {len(only_in_ps)}  → {only_in_ps}")
        print(f"Only in minnie:   {len(only_in_mn)}  → {only_in_mn}")

        df_ps_pd = self._df_ps.select(shared + ["cluster"]).to_pandas()
        df_mn_pd = self._df_mn.select(shared + ["id"]).to_pandas()

        ps_before, mn_before = len(df_ps_pd), len(df_mn_pd)
        df_ps_pd = df_ps_pd.dropna(subset=shared)
        df_mn_pd = df_mn_pd.dropna(subset=shared)

        print(
            f"Patchseq: {ps_before} → {len(df_ps_pd)} rows "
            f"(dropped {ps_before - len(df_ps_pd)})"
        )
        print(
            f"Minnie:   {mn_before} → {len(df_mn_pd)} rows "
            f"(dropped {mn_before - len(df_mn_pd)})"
        )

        self._df_ps_pd = df_ps_pd.reset_index(drop=True)
        self._df_mn_pd = df_mn_pd.reset_index(drop=True)
        self._shared_features = shared
        return self

    # ------------------------------------------------------------------
    # Save harmonised data to h5ad (optional, before scaling)
    # ------------------------------------------------------------------

    def save_harmonized_h5ad(self, output_dir: str) -> "UMAPLabelTransfer":
        """Save patchseq and minnie DataFrames (shared features, pre-scaling) to h5ad.

        Produces two files in *output_dir*:
          - ``{cell_type}_patchseq_harmonized.h5ad``
          - ``{cell_type}_minnie_harmonized.h5ad``

        Call this *after* ``harmonize_features()`` and *before* ``scale()``.
        """
        try:
            import anndata as ad
        except ImportError as exc:
            raise ImportError(
                "anndata is required for save_harmonized_h5ad. "
                "Install it with: pip install anndata"
            ) from exc

        if self._df_ps_pd is None or self._df_mn_pd is None:
            raise RuntimeError("Call harmonize_features() first.")

        os.makedirs(output_dir, exist_ok=True)
        feats = self._shared_features

        # Patchseq: obs columns = id (index) + cluster
        ps_obs = self._df_ps_pd[["cluster"]].copy()
        # Use the DataFrame index as the obs_names; if 'id' is present use it
        if "id" in self._df_ps_pd.columns:
            ps_obs.index = self._df_ps_pd["id"].astype(str)
        adata_ps = ad.AnnData(
            X=self._df_ps_pd[feats].values.astype(np.float32),
            obs=ps_obs,
            var=pd.DataFrame(index=feats),
        )
        ps_path = os.path.join(output_dir, f"{self.cell_type}_patchseq_harmonized.h5ad")
        adata_ps.write_h5ad(ps_path)
        print(f"Saved patchseq h5ad → {ps_path}  {adata_ps.shape}")

        # Minnie: obs column = id
        mn_obs = pd.DataFrame(index=self._df_mn_pd["id"].astype(str))
        adata_mn = ad.AnnData(
            X=self._df_mn_pd[feats].values.astype(np.float32),
            obs=mn_obs,
            var=pd.DataFrame(index=feats),
        )
        mn_path = os.path.join(output_dir, f"{self.cell_type}_minnie_harmonized.h5ad")
        adata_mn.write_h5ad(mn_path)
        print(f"Saved minnie h5ad  → {mn_path}  {adata_mn.shape}")

        return self

    # ------------------------------------------------------------------
    # Phase 3 — Scaling
    # ------------------------------------------------------------------

    def scale(self, method: ScalingMethod = "standard") -> "UMAPLabelTransfer":
        """Scale features.  Fit on patchseq, transform both datasets.

        Parameters
        ----------
        method:
            ``'standard'``  → :class:`sklearn.preprocessing.StandardScaler`
            ``'robust'``    → :class:`sklearn.preprocessing.RobustScaler`
            ``'quantile'``  → :class:`sklearn.preprocessing.QuantileTransformer`
                              (``output_distribution='normal'``, ``n_quantiles=1000``)
        """
        if self._df_ps_pd is None:
            raise RuntimeError("Call harmonize_features() first.")

        if method == "standard":
            scaler = StandardScaler()
        elif method == "robust":
            scaler = RobustScaler()
        elif method == "quantile":
            scaler = QuantileTransformer(
                output_distribution="normal", n_quantiles=1000, random_state=42
            )
        else:
            raise ValueError(
                f"method must be 'standard', 'robust', or 'quantile'; got '{method}'"
            )

        feats = self._shared_features
        X_ps = scaler.fit_transform(self._df_ps_pd[feats].values)
        X_mn = scaler.transform(self._df_mn_pd[feats].values)

        print(f"Scaled patchseq ({method}): {X_ps.shape}")
        print(f"Scaled minnie   ({method}): {X_mn.shape}")

        self._X_ps = X_ps
        self._X_mn = X_mn
        self._scaler = scaler
        self.scaling_method = method
        return self

    # ------------------------------------------------------------------
    # Phase 3 diagnostics
    # ------------------------------------------------------------------

    def plot_alignment_diagnostics(self, top_n: int = 5) -> "UMAPLabelTransfer":
        """Plot per-feature alignment metrics before and after scaling.

        Produces two figures:
        1. Bar chart of |Δ mean| and std ratio (all shared features).
        2. Overlaid histograms for the best- and worst-aligned ``top_n`` features.
        """
        if self._X_ps is None:
            raise RuntimeError("Call scale() first.")

        feats = self._shared_features
        raw_ps = self._df_ps_pd[feats].values
        raw_mn = self._df_mn_pd[feats].values

        mean_ps_raw, mean_mn_raw = raw_ps.mean(0), raw_mn.mean(0)
        std_ps_raw, std_mn_raw = raw_ps.std(0), raw_mn.std(0)
        mean_ps_sc, mean_mn_sc = self._X_ps.mean(0), self._X_mn.mean(0)
        std_ps_sc, std_mn_sc = self._X_ps.std(0), self._X_mn.std(0)

        alignment_df = pd.DataFrame(
            {
                "feature": feats,
                "delta_mean_before": np.abs(mean_ps_raw - mean_mn_raw),
                "delta_mean_after": np.abs(mean_ps_sc - mean_mn_sc),
                "std_ratio_before": std_mn_raw
                / np.where(std_ps_raw == 0, np.nan, std_ps_raw),
                "std_ratio_after": std_mn_sc
                / np.where(std_ps_sc == 0, np.nan, std_ps_sc),
            }
        ).sort_values("delta_mean_after").reset_index(drop=True)

        self._alignment_df = alignment_df

        # ── Figure 1: summary bar chart ───────────────────────────────────
        n_feats = len(alignment_df)
        fig, axes = plt.subplots(
            2, 1, figsize=(max(12, n_feats * 0.55), 8), sharex=True
        )
        x = np.arange(n_feats)
        w = 0.35

        ax = axes[0]
        ax.bar(
            x - w / 2,
            alignment_df["delta_mean_before"],
            width=w,
            color="grey",
            alpha=0.7,
            label="Before scaling",
        )
        ax.bar(
            x + w / 2,
            alignment_df["delta_mean_after"],
            width=w,
            color="teal",
            alpha=0.85,
            label="After scaling",
        )
        ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
        ax.set_ylabel("|Δ mean|  (patchseq − minnie)")
        ax.set_title(
            f"Mean shift per feature — before vs. after {self.scaling_method} scaling  "
            f"(sorted by post-scaling Δmean)"
        )
        ax.legend()

        ax = axes[1]
        ax.bar(
            x - w / 2,
            alignment_df["std_ratio_before"],
            width=w,
            color="grey",
            alpha=0.7,
            label="Before scaling",
        )
        ax.bar(
            x + w / 2,
            alignment_df["std_ratio_after"],
            width=w,
            color="teal",
            alpha=0.85,
            label="After scaling",
        )
        ax.axhline(1, color="black", linewidth=0.8, linestyle="--", label="Ideal = 1")
        ax.set_ylabel("std(minnie) / std(patchseq)")
        ax.set_title(f"Std ratio per feature — before vs. after {self.scaling_method} scaling")
        ax.set_xticks(x)
        ax.set_xticklabels(alignment_df["feature"], rotation=45, ha="right", fontsize=8)
        ax.legend()
        fig.tight_layout()
        plt.show()

        # ── Figure 2: per-feature overlaid histograms ─────────────────────
        top_n = min(top_n, len(alignment_df) // 2)
        N_BINS = 40
        best_feats = alignment_df.head(top_n)["feature"].tolist()
        worst_feats = alignment_df.tail(top_n)["feature"].tolist()
        plot_feats = best_feats + worst_feats
        sections = ["best"] * top_n + ["worst"] * top_n
        BG = {"best": "#f0fff0", "worst": "#fff0f0"}

        fig2, axes2 = plt.subplots(
            len(plot_feats), 2, figsize=(12, len(plot_feats) * 2.2), squeeze=False
        )
        fig2.suptitle(
            f"Best/Worst Aligned Features — Before vs. After {self.scaling_method} Scaling\n"
            "(left = raw values,  right = scaled)\n"
            "dashed lines = per-dataset mean",
            fontsize=11,
        )

        for row_i, (feat, section) in enumerate(zip(plot_feats, sections)):
            feat_idx = feats.index(feat)
            row = alignment_df.loc[alignment_df["feature"] == feat].iloc[0]
            ps_raw = self._df_ps_pd[feat].values
            mn_raw = self._df_mn_pd[feat].values
            ps_sc = self._X_ps[:, feat_idx]
            mn_sc = self._X_mn[:, feat_idx]

            for col_i, (ps_v, mn_v, subtitle, delta) in enumerate(
                [
                    (ps_raw, mn_raw, "Before scaling (raw)", row["delta_mean_before"]),
                    (ps_sc, mn_sc, "After scaling", row["delta_mean_after"]),
                ]
            ):
                combined_min = min(ps_v.min(), mn_v.min())
                combined_max = max(ps_v.max(), mn_v.max())
                bins = np.linspace(combined_min, combined_max, N_BINS + 1)
                ax = axes2[row_i, col_i]
                ax.set_facecolor(BG[section])
                ax.hist(ps_v, bins=bins, density=True, alpha=0.5, color="steelblue", label="patchseq")
                ax.hist(mn_v, bins=bins, density=True, alpha=0.5, color="darkorange", label="minnie")
                ax.axvline(ps_v.mean(), color="steelblue", linestyle="--", linewidth=1.2)
                ax.axvline(mn_v.mean(), color="darkorange", linestyle="--", linewidth=1.2)
                ax.set_title(f"{feat}   Δmean={delta:.3f}   [{subtitle}]", fontsize=8)
                ax.set_ylabel("density", fontsize=7)
                if row_i == 0 and col_i == 0:
                    ax.legend(fontsize=8)

        fig2.tight_layout()
        plt.show()
        return self

    # ------------------------------------------------------------------
    # Phase 4 — UMAP projection
    # ------------------------------------------------------------------

    def fit_umap(
        self, mode: UMAPMode = "unsupervised", **umap_kwargs
    ) -> "UMAPLabelTransfer":
        """Fit UMAP on patchseq and project minnie into the same space.

        Parameters
        ----------
        mode:
            ``'unsupervised'`` — standard UMAP, no label guidance.
            ``'supervised'``   — label-guided UMAP using patchseq cluster labels.
        **umap_kwargs:
            Extra keyword arguments forwarded to ``umap.UMAP()``.
            They override the defaults but are merged with them, so you only
            need to specify what you want to change.
        """
        if self._X_ps is None:
            raise RuntimeError("Call scale() first.")

        if mode == "unsupervised":
            defaults = dict(n_components=2, random_state=42, init="random")
            defaults.update(umap_kwargs)
            reducer = umap.UMAP(**defaults)
            ps_emb = reducer.fit_transform(self._X_ps)
            mn_emb = reducer.transform(self._X_mn)

        elif mode == "supervised":
            le = LabelEncoder()
            ps_labels_enc = le.fit_transform(self._df_ps_pd["cluster"].values)
            defaults = dict(n_components=2, random_state=42, init="spectral", n_jobs=1)
            defaults.update(umap_kwargs)
            reducer = umap.UMAP(**defaults)
            ps_emb = reducer.fit_transform(self._X_ps, y=ps_labels_enc)
            mn_emb = reducer.transform(self._X_mn)

        else:
            raise ValueError(
                f"mode must be 'unsupervised' or 'supervised'; got '{mode}'"
            )

        print(f"Patchseq embedding ({mode}): {ps_emb.shape}")
        print(f"Minnie embedding   ({mode}): {mn_emb.shape}")

        self._reducer = reducer
        self._ps_emb = ps_emb
        self._mn_emb = mn_emb
        self.umap_mode = mode
        return self

    # ------------------------------------------------------------------
    # Phase 5 — KNN label transfer
    # ------------------------------------------------------------------

    def transfer_labels(self, k: int = 3) -> "UMAPLabelTransfer":
        """Majority-vote KNN label transfer from patchseq to minnie.

        Parameters
        ----------
        k:
            Number of nearest neighbours.  Default 3.
        """
        if self._ps_emb is None:
            raise RuntimeError("Call fit_umap() first.")

        ps_labels = self._df_ps_pd["cluster"].values

        knn = NearestNeighbors(n_neighbors=k)
        knn.fit(self._ps_emb)
        _, indices = knn.kneighbors(self._mn_emb)

        neighbor_labels = ps_labels[indices]  # (n_minnie, k)
        mn_predicted = np.array(
            [Counter(row).most_common(1)[0][0] for row in neighbor_labels]
        )

        print("Minnie predicted label counts:")
        unique, counts = np.unique(mn_predicted, return_counts=True)
        for lbl, cnt in sorted(zip(unique, counts), key=lambda x: -x[1]):
            print(f"  {lbl:<50} {cnt}")

        self._ps_labels = ps_labels
        self._mn_predicted = mn_predicted
        return self

    # ------------------------------------------------------------------
    # Phase 6 — Visualisation
    # ------------------------------------------------------------------

    def plot_umap(self) -> "UMAPLabelTransfer":
        """Three-panel UMAP figure.

        Left  : both datasets coloured by dataset identity.
        Middle: patchseq cells coloured by true cluster label.
        Right : minnie cells coloured by predicted cluster label.
        """
        if self._mn_predicted is None:
            raise RuntimeError("Call transfer_labels() first.")

        ps_labels = self._ps_labels
        mn_predicted = self._mn_predicted
        ps_emb = self._ps_emb
        mn_emb = self._mn_emb

        all_labels = sorted(set(ps_labels) | set(mn_predicted))
        cmap20 = plt.get_cmap("tab20")
        cluster_colors = {
            lbl: cmap20(i / max(len(all_labels) - 1, 1))
            for i, lbl in enumerate(all_labels)
        }
        DS_COLORS = {"patchseq": "#1f77b4", "minnie65": "#ff7f0e"}

        fig, axes = plt.subplots(1, 3, figsize=(18, 6))

        # Left panel — dataset identity
        ax = axes[0]
        ax.scatter(
            mn_emb[:, 0], mn_emb[:, 1],
            c=DS_COLORS["minnie65"], s=1.5, alpha=0.5, rasterized=True, label="minnie65",
        )
        ax.scatter(
            ps_emb[:, 0], ps_emb[:, 1],
            c=DS_COLORS["patchseq"], s=1.5, alpha=0.7, rasterized=True, label="patchseq",
        )
        ax.set_title("Both datasets")
        ax.set_xlabel("UMAP 1")
        ax.set_ylabel("UMAP 2")
        ax.legend(markerscale=5, framealpha=0.7, fontsize=9)

        # Middle panel — patchseq true labels
        ax = axes[1]
        for lbl in all_labels:
            mask = ps_labels == lbl
            if mask.any():
                ax.scatter(
                    ps_emb[mask, 0], ps_emb[mask, 1],
                    c=[cluster_colors[lbl]], s=1.5, alpha=0.7, rasterized=True,
                )
        ax.set_title("Patchseq — true labels")
        ax.set_xlabel("UMAP 1")
        ax.set_ylabel("UMAP 2")

        # Right panel — minnie predicted labels
        ax = axes[2]
        for lbl in all_labels:
            mask = mn_predicted == lbl
            if mask.any():
                ax.scatter(
                    mn_emb[mask, 0], mn_emb[mask, 1],
                    c=[cluster_colors[lbl]], s=1.5, alpha=0.7, rasterized=True,
                )
        ax.set_title("Minnie — predicted labels")
        ax.set_xlabel("UMAP 1")
        ax.set_ylabel("UMAP 2")

        # Shared legend
        handles = [
            mpatches.Patch(color=cluster_colors[lbl], label=lbl)
            for lbl in all_labels
        ]
        fig.legend(
            handles=handles,
            title="Cluster",
            loc="lower center",
            ncol=min(len(all_labels), 6),
            bbox_to_anchor=(0.5, -0.15),
            framealpha=0.8,
            fontsize=8,
        )

        cell_label = self.cell_type.upper()
        mode_label = self.umap_mode
        plt.suptitle(
            f"UMAP Label Transfer: patchseq (VISp {cell_label}) → minnie65 ({cell_label})"
            f"  [{mode_label}]",
            fontsize=13,
        )
        plt.tight_layout()
        plt.show()
        return self

    # ------------------------------------------------------------------
    # Convenience: full pipeline
    # ------------------------------------------------------------------

    def run(
        self,
        scaling_method: ScalingMethod = "standard",
        umap_mode: UMAPMode = "unsupervised",
        h5ad_output_dir: str | None = None,
        k: int = 3,
        plot_diagnostics: bool = True,
    ) -> "UMAPLabelTransfer":
        """Run the full pipeline end-to-end.

        Parameters
        ----------
        scaling_method:
            Passed to :meth:`scale`.
        umap_mode:
            Passed to :meth:`fit_umap`.
        h5ad_output_dir:
            If given, calls :meth:`save_harmonized_h5ad` (after harmonisation,
            before scaling).
        k:
            Number of KNN neighbours for label transfer.
        plot_diagnostics:
            Whether to call :meth:`plot_alignment_diagnostics` after scaling.
        """
        self.load_data()
        self.harmonize_features()
        if h5ad_output_dir is not None:
            self.save_harmonized_h5ad(h5ad_output_dir)
        self.scale(method=scaling_method)
        if plot_diagnostics:
            self.plot_alignment_diagnostics()
        self.fit_umap(mode=umap_mode)
        self.transfer_labels(k=k)
        self.plot_umap()
        return self
