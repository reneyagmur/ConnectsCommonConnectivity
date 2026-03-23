"""Generalised label transfer between two user-defined Delta Lake feature datasets.

Encapsulates the same 6-phase pipeline as UMAPLabelTransfer but with no
hardcoded exc/inh configuration and a pluggable transfer method:

    Phase 1 — Load data
    Phase 2 — Feature harmonisation
    Phase 3 — Scaling  (standard | robust | quantile)
    Phase 4 — Projection  (umap: unsupervised | supervised)
    Phase 5 — KNN label transfer
    Phase 6 — Visualisation / output

Usage (quick):
    from label_transfer import LabelTransfer

    lt = LabelTransfer(
        data_root='/data/microns1412/',
        source_features_subpath='cellfeatures/exc_morph_features',
        source_project_id='visp_exc_patchseq',
        source_feature_set_id='exc_visp_morph_features',
        target_features_subpath='cellfeatures/minnie_exc_skel_keys',
        target_project_id='minnie65',
        target_feature_set_id='minnie_exc_skel_keys',
    )
    result_df = lt.run(scaling_method='standard', umap_mode='supervised')

Usage (step-by-step):
    lt = LabelTransfer(...)
    lt.load_data()
    lt.harmonize_features()
    lt.save_harmonized_h5ad('/path/to/output')   # optional
    lt.scale(method='robust')
    lt.plot_alignment_diagnostics()
    lt.fit(mode='supervised')
    lt.transfer_labels(k=3)
    lt.plot_umap()
    result_df = lt.predict()
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
# Type aliases
# ---------------------------------------------------------------------------

_META_COLS = {"id", "project_id", "feature_set_id", "cluster"}

ScalingMethod = Literal["standard", "robust", "quantile"]
UMAPMode = Literal["unsupervised", "supervised"]
TransferMethod = Literal["umap"]


class LabelTransfer:
    """Generalised label transfer from a labeled source dataset to an unlabeled target.

    Parameters
    ----------
    data_root:
        Root path containing all Delta Lake tables.
    source_features_subpath:
        Relative path (under *data_root*) to the source feature table.
    source_project_id:
        ``project_id`` filter value for the source feature table.
        Also used to filter the ``clustermembership`` table.
    source_feature_set_id:
        ``feature_set_id`` filter value for the source feature table.
    target_features_subpath:
        Relative path (under *data_root*) to the target feature table.
    target_project_id:
        ``project_id`` filter value for the target feature table.
    target_feature_set_id:
        ``feature_set_id`` filter value for the target feature table.
    source_label_taxonomy_project_id:
        ``project_id`` used to filter the ``cluster`` table when loading
        source labels.  Defaults to ``'visp_met_types'``.
    method:
        Transfer method.  Only ``'umap'`` is currently implemented.
    """

    def __init__(
        self,
        data_root: str,
        source_features_subpath: str,
        source_project_id: str,
        source_feature_set_id: str,
        target_features_subpath: str,
        target_project_id: str,
        target_feature_set_id: str,
        source_label_taxonomy_project_id: str = "visp_met_types",
        method: TransferMethod = "umap",
    ) -> None:
        if method != "umap":
            raise NotImplementedError(
                f"method='{method}' is not implemented. Only 'umap' is supported."
            )

        self.data_root = data_root
        self.source_features_subpath = source_features_subpath
        self.source_project_id = source_project_id
        self.source_feature_set_id = source_feature_set_id
        self.target_features_subpath = target_features_subpath
        self.target_project_id = target_project_id
        self.target_feature_set_id = target_feature_set_id
        self.source_label_taxonomy_project_id = source_label_taxonomy_project_id
        self.method = method

        # State populated by each phase
        self._df_source_feat: pl.DataFrame | None = None
        self._df_source: pl.DataFrame | None = None
        self._df_target: pl.DataFrame | None = None
        self._df_source_pd: pd.DataFrame | None = None
        self._df_target_pd: pd.DataFrame | None = None
        self._shared_features: list[str] | None = None
        self._X_source: np.ndarray | None = None
        self._X_target: np.ndarray | None = None
        self._scaler = None
        self.scaling_method: str | None = None
        self._alignment_df: pd.DataFrame | None = None
        self._reducer = None
        self._source_emb: np.ndarray | None = None
        self._target_emb: np.ndarray | None = None
        self.umap_mode: str | None = None
        self._source_labels: np.ndarray | None = None
        self._target_predicted: np.ndarray | None = None
        self._cluster_colors: dict[str, str] | None = None

    # ------------------------------------------------------------------
    # Phase 1 — Data loading
    # ------------------------------------------------------------------

    def _load_features(
        self, subpath: str, project_id: str, feature_set_id: str
    ) -> pl.DataFrame:
        """Load and filter a feature table from Delta Lake."""
        path = os.path.join(self.data_root, subpath)
        return pl.read_delta(path).filter(
            (pl.col("project_id") == project_id)
            & (pl.col("feature_set_id") == feature_set_id)
        )

    def load_source(self) -> "LabelTransfer":
        """Load source features, then join cluster labels onto them."""
        df_feat = self._load_features(
            self.source_features_subpath,
            self.source_project_id,
            self.source_feature_set_id,
        )
        print(f"Source features: {df_feat.shape}")
        self._df_source_feat = df_feat
        self._load_labels()
        return self

    def _load_labels(self) -> None:
        """Load source cluster labels and inner-join onto source features.

        Strategy: load ``clustermembership`` filtered by ``source_project_id``
        + ``cluster`` table filtered by ``source_label_taxonomy_project_id``,
        keep the deepest (highest ``level``) label per cell, then inner-join
        onto ``self._df_source_feat``.
        """
        df_cm = pl.read_delta(
            os.path.join(self.data_root, "clustermembership")
        ).filter(pl.col("project_id") == self.source_project_id)

        df_clusters = pl.read_delta(
            os.path.join(self.data_root, "cluster")
        ).filter(pl.col("project_id") == self.source_label_taxonomy_project_id)

        if "hex_color" in df_clusters.columns:
            self._cluster_colors = dict(
                zip(df_clusters["id"].to_list(), df_clusters["hex_color"].to_list())
            )
        else:
            self._cluster_colors = {}

        df_labels = (
            df_cm.select(["item", "cluster"])
            .join(
                df_clusters.select(["id", "level", "heirachy_category"]),
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
            f"Unique source cells: {df_labels['item'].n_unique()}, "
            f"unique labels: {df_labels['cluster'].n_unique()}"
        )

        df_source = self._df_source_feat.join(
            df_labels, left_on="id", right_on="item", how="inner"
        )
        print(f"Source after label join: {df_source.shape}")
        self._df_source = df_source

    def load_target(self) -> "LabelTransfer":
        """Load target features from Delta Lake."""
        df = self._load_features(
            self.target_features_subpath,
            self.target_project_id,
            self.target_feature_set_id,
        )
        print(f"Target features: {df.shape}")
        self._df_target = df
        return self

    def load_data(self) -> "LabelTransfer":
        """Convenience wrapper: load source (features + labels) and target features."""
        self.load_source()
        self.load_target()
        return self

    # ------------------------------------------------------------------
    # Phase 2 — Feature harmonisation
    # ------------------------------------------------------------------

    def harmonize_features(self) -> "LabelTransfer":
        """Identify shared features, subset both datasets, drop NaN rows."""
        if self._df_source is None or self._df_target is None:
            raise RuntimeError("Call load_data() first.")

        src_feat_cols = [c for c in self._df_source.columns if c not in _META_COLS]
        tgt_feat_cols = [c for c in self._df_target.columns if c not in _META_COLS]

        only_in_source, only_in_target = get_list_differences(
            src_feat_cols, tgt_feat_cols, return_lists=True, print_lists=False
        )
        shared = sorted(set(src_feat_cols) & set(tgt_feat_cols))

        print(f"Shared features:  {len(shared)}")
        print(f"Only in source:   {len(only_in_source)}  → {only_in_source}")
        print(f"Only in target:   {len(only_in_target)}  → {only_in_target}")

        df_src_pd = self._df_source.select(shared + ["cluster"]).to_pandas()
        df_tgt_pd = self._df_target.select(shared + ["id"]).to_pandas()

        src_before, tgt_before = len(df_src_pd), len(df_tgt_pd)
        df_src_pd = df_src_pd.dropna(subset=shared)
        df_tgt_pd = df_tgt_pd.dropna(subset=shared)

        print(
            f"Source: {src_before} → {len(df_src_pd)} rows "
            f"(dropped {src_before - len(df_src_pd)})"
        )
        print(
            f"Target: {tgt_before} → {len(df_tgt_pd)} rows "
            f"(dropped {tgt_before - len(df_tgt_pd)})"
        )

        self._df_source_pd = df_src_pd.reset_index(drop=True)
        self._df_target_pd = df_tgt_pd.reset_index(drop=True)
        self._shared_features = shared
        return self

    # ------------------------------------------------------------------
    # Save harmonised data to h5ad (optional, before scaling)
    # ------------------------------------------------------------------

    def save_harmonized_h5ad(self, output_dir: str) -> "LabelTransfer":
        """Save source and target DataFrames (shared features, pre-scaling) to h5ad.

        Produces two files in *output_dir*:
          - ``source_harmonized.h5ad``
          - ``target_harmonized.h5ad``

        Call this *after* ``harmonize_features()`` and *before* ``scale()``.
        """
        try:
            import anndata as ad
        except ImportError as exc:
            raise ImportError(
                "anndata is required for save_harmonized_h5ad. "
                "Install it with: pip install anndata"
            ) from exc

        if self._df_source_pd is None or self._df_target_pd is None:
            raise RuntimeError("Call harmonize_features() first.")

        os.makedirs(output_dir, exist_ok=True)
        feats = self._shared_features

        src_obs = self._df_source_pd[["cluster"]].copy()
        if "id" in self._df_source_pd.columns:
            src_obs.index = self._df_source_pd["id"].astype(str)
        adata_src = ad.AnnData(
            X=self._df_source_pd[feats].values.astype(np.float32),
            obs=src_obs,
            var=pd.DataFrame(index=feats),
        )
        src_path = os.path.join(output_dir, "source_harmonized.h5ad")
        adata_src.write_h5ad(src_path)
        print(f"Saved source h5ad → {src_path}  {adata_src.shape}")

        tgt_obs = pd.DataFrame(index=self._df_target_pd["id"].astype(str))
        adata_tgt = ad.AnnData(
            X=self._df_target_pd[feats].values.astype(np.float32),
            obs=tgt_obs,
            var=pd.DataFrame(index=feats),
        )
        tgt_path = os.path.join(output_dir, "target_harmonized.h5ad")
        adata_tgt.write_h5ad(tgt_path)
        print(f"Saved target h5ad  → {tgt_path}  {adata_tgt.shape}")

        return self

    # ------------------------------------------------------------------
    # Phase 3 — Scaling
    # ------------------------------------------------------------------

    def scale(self, method: ScalingMethod = "standard") -> "LabelTransfer":
        """Scale features.  Fit on source, transform both datasets.

        Parameters
        ----------
        method:
            ``'standard'``  → :class:`sklearn.preprocessing.StandardScaler`
            ``'robust'``    → :class:`sklearn.preprocessing.RobustScaler`
            ``'quantile'``  → :class:`sklearn.preprocessing.QuantileTransformer`
                              (``output_distribution='normal'``, ``n_quantiles=1000``)
        """
        if self._df_source_pd is None:
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
        X_source = scaler.fit_transform(self._df_source_pd[feats].values)
        X_target = scaler.transform(self._df_target_pd[feats].values)

        print(f"Scaled source ({method}): {X_source.shape}")
        print(f"Scaled target ({method}): {X_target.shape}")

        self._X_source = X_source
        self._X_target = X_target
        self._scaler = scaler
        self.scaling_method = method
        return self

    # ------------------------------------------------------------------
    # Phase 3 diagnostics
    # ------------------------------------------------------------------

    def plot_alignment_diagnostics(self, top_n: int = 5) -> "LabelTransfer":
        """Plot per-feature alignment metrics before and after scaling.

        Produces two figures:
        1. Bar chart of |Δ mean| and std ratio (all shared features).
        2. Overlaid histograms for the best- and worst-aligned ``top_n`` features.
        """
        if self._X_source is None:
            raise RuntimeError("Call scale() first.")

        feats = self._shared_features
        raw_src = self._df_source_pd[feats].values
        raw_tgt = self._df_target_pd[feats].values

        mean_src_raw, mean_tgt_raw = raw_src.mean(0), raw_tgt.mean(0)
        std_src_raw, std_tgt_raw = raw_src.std(0), raw_tgt.std(0)
        mean_src_sc, mean_tgt_sc = self._X_source.mean(0), self._X_target.mean(0)
        std_src_sc, std_tgt_sc = self._X_source.std(0), self._X_target.std(0)

        alignment_df = pd.DataFrame(
            {
                "feature": feats,
                "delta_mean_before": np.abs(mean_src_raw - mean_tgt_raw),
                "delta_mean_after": np.abs(mean_src_sc - mean_tgt_sc),
                "std_ratio_before": std_tgt_raw
                / np.where(std_src_raw == 0, np.nan, std_src_raw),
                "std_ratio_after": std_tgt_sc
                / np.where(std_src_sc == 0, np.nan, std_src_sc),
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
        ax.set_ylabel("|Δ mean|  (source − target)")
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
        ax.set_ylabel("std(target) / std(source)")
        ax.set_title(
            f"Std ratio per feature — before vs. after {self.scaling_method} scaling"
        )
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
            src_raw = self._df_source_pd[feat].values
            tgt_raw = self._df_target_pd[feat].values
            src_sc = self._X_source[:, feat_idx]
            tgt_sc = self._X_target[:, feat_idx]

            for col_i, (src_v, tgt_v, subtitle, delta) in enumerate(
                [
                    (src_raw, tgt_raw, "Before scaling (raw)", row["delta_mean_before"]),
                    (src_sc, tgt_sc, "After scaling", row["delta_mean_after"]),
                ]
            ):
                combined_min = min(src_v.min(), tgt_v.min())
                combined_max = max(src_v.max(), tgt_v.max())
                bins = np.linspace(combined_min, combined_max, N_BINS + 1)
                ax = axes2[row_i, col_i]
                ax.set_facecolor(BG[section])
                ax.hist(
                    src_v, bins=bins, density=True, alpha=0.5,
                    color="steelblue", label="source",
                )
                ax.hist(
                    tgt_v, bins=bins, density=True, alpha=0.5,
                    color="darkorange", label="target",
                )
                ax.axvline(src_v.mean(), color="steelblue", linestyle="--", linewidth=1.2)
                ax.axvline(tgt_v.mean(), color="darkorange", linestyle="--", linewidth=1.2)
                ax.set_title(f"{feat}   Δmean={delta:.3f}   [{subtitle}]", fontsize=8)
                ax.set_ylabel("density", fontsize=7)
                if row_i == 0 and col_i == 0:
                    ax.legend(fontsize=8)

        fig2.tight_layout()
        plt.show()
        return self

    # ------------------------------------------------------------------
    # Phase 4 — Projection (method dispatch)
    # ------------------------------------------------------------------

    def fit(self, mode: UMAPMode = "unsupervised", **kwargs) -> "LabelTransfer":
        """Fit the projection model on source and transform target into the same space.

        Parameters
        ----------
        mode:
            ``'unsupervised'`` or ``'supervised'``.  Passed to the underlying
            method implementation.
        **kwargs:
            Extra keyword arguments forwarded to the underlying method.
        """
        if self.method == "umap":
            return self._fit_umap(mode=mode, **kwargs)
        raise NotImplementedError(
            f"method='{self.method}' is not implemented. Only 'umap' is supported."
        )

    def _fit_umap(self, mode: UMAPMode = "unsupervised", **umap_kwargs) -> "LabelTransfer":
        """Fit UMAP on source and project target into the same embedding space.

        Parameters
        ----------
        mode:
            ``'unsupervised'`` — standard UMAP, no label guidance.
            ``'supervised'``   — label-guided UMAP using source cluster labels.
        **umap_kwargs:
            Extra keyword arguments forwarded to ``umap.UMAP()``.
        """
        if self._X_source is None:
            raise RuntimeError("Call scale() first.")

        if mode == "unsupervised":
            defaults = dict(n_components=2, random_state=42, init="random")
            defaults.update(umap_kwargs)
            reducer = umap.UMAP(**defaults)
            source_emb = reducer.fit_transform(self._X_source)
            target_emb = reducer.transform(self._X_target)

        elif mode == "supervised":
            le = LabelEncoder()
            source_labels_enc = le.fit_transform(self._df_source_pd["cluster"].values)
            defaults = dict(n_components=2, random_state=42, init="spectral", n_jobs=1)
            defaults.update(umap_kwargs)
            reducer = umap.UMAP(**defaults)
            source_emb = reducer.fit_transform(self._X_source, y=source_labels_enc)
            target_emb = reducer.transform(self._X_target)

        else:
            raise ValueError(
                f"mode must be 'unsupervised' or 'supervised'; got '{mode}'"
            )

        print(f"Source embedding ({mode}): {source_emb.shape}")
        print(f"Target embedding ({mode}): {target_emb.shape}")

        self._reducer = reducer
        self._source_emb = source_emb
        self._target_emb = target_emb
        self.umap_mode = mode
        return self

    # ------------------------------------------------------------------
    # Phase 5 — KNN label transfer
    # ------------------------------------------------------------------

    def transfer_labels(self, k: int = 3) -> "LabelTransfer":
        """Majority-vote KNN label transfer from source to target.

        Parameters
        ----------
        k:
            Number of nearest neighbours.  Default 3.
        """
        if self._source_emb is None:
            raise RuntimeError("Call fit() first.")

        source_labels = self._df_source_pd["cluster"].values

        knn = NearestNeighbors(n_neighbors=k)
        knn.fit(self._source_emb)
        _, indices = knn.kneighbors(self._target_emb)

        neighbor_labels = source_labels[indices]  # (n_target, k)
        target_predicted = np.array(
            [Counter(row).most_common(1)[0][0] for row in neighbor_labels]
        )

        print("Target predicted label counts:")
        unique, counts = np.unique(target_predicted, return_counts=True)
        for lbl, cnt in sorted(zip(unique, counts), key=lambda x: -x[1]):
            print(f"  {lbl:<50} {cnt}")

        self._source_labels = source_labels
        self._target_predicted = target_predicted
        return self

    # ------------------------------------------------------------------
    # Phase 6 — Output
    # ------------------------------------------------------------------

    def predict(self) -> pd.DataFrame:
        """Return a DataFrame of target cell IDs and their predicted labels.

        Returns
        -------
        pd.DataFrame
            Columns: ``['id', 'predicted_label']``.
        """
        if self._target_predicted is None:
            raise RuntimeError("Call transfer_labels() first.")

        return pd.DataFrame(
            {
                "id": self._df_target_pd["id"].values,
                "predicted_label": self._target_predicted,
            }
        )

    # ------------------------------------------------------------------
    # Phase 6 — Visualisation
    # ------------------------------------------------------------------

    def plot_umap(self) -> "LabelTransfer":
        """Three-panel UMAP figure.

        Left  : both datasets coloured by dataset identity.
        Middle: source cells coloured by true cluster label.
        Right : target cells coloured by predicted cluster label.
        """
        if self._target_predicted is None:
            raise RuntimeError("Call transfer_labels() first.")

        source_labels = self._source_labels
        target_predicted = self._target_predicted
        source_emb = self._source_emb
        target_emb = self._target_emb

        all_labels = sorted(set(source_labels) | set(target_predicted))

        known_colors = self._cluster_colors or {}
        cmap20 = plt.get_cmap("tab20")
        fallback_labels = [lbl for lbl in all_labels if lbl not in known_colors]
        fallback_colors = {
            lbl: cmap20(i / max(len(fallback_labels) - 1, 1))
            for i, lbl in enumerate(fallback_labels)
        }
        cluster_colors = {
            **fallback_colors,
            **{lbl: known_colors[lbl] for lbl in all_labels if lbl in known_colors},
        }

        DS_COLORS = {"source": "#1f77b4", "target": "#ff7f0e"}

        fig, axes = plt.subplots(1, 3, figsize=(18, 6))

        # Left panel — dataset identity
        ax = axes[0]
        ax.scatter(
            target_emb[:, 0], target_emb[:, 1],
            c=DS_COLORS["target"], s=1.5, alpha=0.5, rasterized=True, label="target",
        )
        ax.scatter(
            source_emb[:, 0], source_emb[:, 1],
            c=DS_COLORS["source"], s=1.5, alpha=0.7, rasterized=True, label="source",
        )
        ax.set_title("Both datasets")
        ax.set_xlabel("UMAP 1")
        ax.set_ylabel("UMAP 2")
        ax.legend(markerscale=5, framealpha=0.7, fontsize=9)

        # Middle panel — source true labels
        ax = axes[1]
        for lbl in all_labels:
            mask = source_labels == lbl
            if mask.any():
                ax.scatter(
                    source_emb[mask, 0], source_emb[mask, 1],
                    c=[cluster_colors[lbl]], s=1.5, alpha=0.7, rasterized=True,
                )
        ax.set_title("Source — true labels")
        ax.set_xlabel("UMAP 1")
        ax.set_ylabel("UMAP 2")

        # Right panel — target predicted labels
        ax = axes[2]
        for lbl in all_labels:
            mask = target_predicted == lbl
            if mask.any():
                ax.scatter(
                    target_emb[mask, 0], target_emb[mask, 1],
                    c=[cluster_colors[lbl]], s=1.5, alpha=0.7, rasterized=True,
                )
        ax.set_title("Target — predicted labels")
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

        plt.suptitle(
            f"UMAP Label Transfer: source → target  [{self.umap_mode}]",
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
    ) -> pd.DataFrame:
        """Run the full pipeline end-to-end and return the prediction DataFrame.

        Parameters
        ----------
        scaling_method:
            Passed to :meth:`scale`.
        umap_mode:
            Passed to :meth:`fit`.
        h5ad_output_dir:
            If given, calls :meth:`save_harmonized_h5ad` after harmonisation
            and before scaling.
        k:
            Number of KNN neighbours for label transfer.
        plot_diagnostics:
            Whether to call :meth:`plot_alignment_diagnostics` after scaling.

        Returns
        -------
        pd.DataFrame
            Columns: ``['id', 'predicted_label']``.
        """
        self.load_data()
        self.harmonize_features()
        if h5ad_output_dir is not None:
            self.save_harmonized_h5ad(h5ad_output_dir)
        self.scale(method=scaling_method)
        if plot_diagnostics:
            self.plot_alignment_diagnostics()
        self.fit(mode=umap_mode)
        self.transfer_labels(k=k)
        self.plot_umap()
        return self.predict()
