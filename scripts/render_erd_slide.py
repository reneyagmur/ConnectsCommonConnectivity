#!/usr/bin/env python3
"""Render a grouped presentation ERD (16:9) and a Mermaid flowchart version.

Outputs:
  docs/erd_slide.png          -- matplotlib 16:9 slide image (300 DPI)
  docs/erd_slide.mmd          -- Mermaid flowchart source
  docs/erd_slide_config.json  -- Mermaid config with color CSS
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, field

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

DOCS_DIR = pathlib.Path(__file__).resolve().parent.parent / "docs"

# ── Module definitions ─────────────────────────────────────────────────

@dataclass
class Module:
    key: str
    label: str
    entities: list[str]
    header_color: str
    body_color: str
    x: float = 0
    y: float = 0

MODULES = [
    Module("core", "Core",
           ["DataSet", "DataItem", "DataItemDataSetAssociation", "SpatialLocation"],
           "#4472C4", "#D6E4F0"),
    Module("storage", "Storage",
           ["ZarrArray", "ZarrDataset", "ParquetDataset"],
           "#548235", "#E2EFDA"),
    Module("brain_region", "Brain Region",
           ["BrainRegion", "BrainRegionAssociation"],
           "#BF8F00", "#FFF2CC"),
    Module("clustering", "Clustering",
           ["AlgorithmRun", "ClusterHierarchy", "Cluster",
            "ClusterMembership", "HierachyCategory"],
           "#7030A0", "#E2D1F0"),
    Module("projection", "Projection",
           ["ProjectionMeasurementMatrix"],
           "#C55A11", "#FCE4D6"),
    Module("cell_cell", "Cell-Cell Connectivity",
           ["CellCellConnectivityLong", "CellCellMeasurementMatrix"],
           "#C00000", "#F4CCCC"),
    Module("cell_gene", "Cell-Gene Expression",
           ["CellGeneData", "BarcodingExperimentMetadata",
            "GeneMetadata", "CellMetadata"],
           "#0070C0", "#DAEEF3"),
    Module("cell_features", "Cell Features",
           ["CellFeatureSet", "CellFeatureDefinition",
            "CellFeatureMatrix", "CellFeatureMeasurement"],
           "#00B050", "#D9F2E6"),
    Module("single_cell", "Single Cell",
           ["SingleCellReconstruction"],
           "#606060", "#E0E0E0"),
    Module("mappings", "Mappings",
           ["MappingSet", "CellToCellMapping",
            "CellToClusterMapping", "ClusterToClusterMapping"],
           "#9C5700", "#FBE5D6"),
]

MODULE_MAP = {m.key: m for m in MODULES}

@dataclass
class Edge:
    source: str
    target: str
    label: str

EDGES = [
    Edge("clustering",    "core",        "input_dataset, item"),
    Edge("brain_region",  "core",        "dataitem_id"),
    Edge("projection",    "core",        "data_item_index"),
    Edge("cell_cell",     "core",        "pre/postsynaptic cell"),
    Edge("cell_gene",     "core",        "dataitem_id"),
    Edge("cell_features", "core",        "dataitem_id"),
    Edge("single_cell",   "core",        "id, soma_location"),
    Edge("mappings",      "core",        "source/target cell"),
    Edge("projection",    "storage",     "values (Zarr)"),
    Edge("cell_cell",     "storage",     "values (Zarr)"),
    Edge("cell_gene",     "storage",     "matrix, metadata"),
    Edge("cell_features", "storage",     "parquet_path"),
    Edge("projection",    "brain_region","region_index"),
    Edge("mappings",      "clustering",  "source/target cluster"),
]

# ── Layout (manual grid, 16:9 proportions) ─────────────────────────────

BOX_W = 2.9
BOX_PAD = 0.15
HEADER_H = 0.40
ROW_H = 0.26
HEADER_FONT = 11.5
ENTITY_FONT = 8.5
EDGE_LABEL_FONT = 5.8

def box_height(m: Module) -> float:
    return HEADER_H + len(m.entities) * ROW_H + BOX_PAD * 2

def assign_positions():
    """Place modules in a hand-tuned 3-row layout for 16:9."""
    # Row 0 (top):    Core, Storage, Brain Region, Single Cell
    # Row 1 (middle): Clustering, Projection, Cell-Cell, Cell-Gene
    # Row 2 (bottom): Mappings, Cell Features

    col_xs = [0.4, 4.0, 7.6, 11.6]
    row_ys = [0.3, 3.5, 6.3]

    placements = {
        "core":          (col_xs[0], row_ys[0]),
        "storage":       (col_xs[1], row_ys[0]),
        "brain_region":  (col_xs[2], row_ys[0]),
        "single_cell":   (col_xs[3], row_ys[0]),
        "clustering":    (col_xs[0], row_ys[1]),
        "projection":    (col_xs[1], row_ys[1]),
        "cell_cell":     (col_xs[2], row_ys[1]),
        "cell_gene":     (col_xs[3], row_ys[1]),
        "mappings":      (col_xs[0], row_ys[2]),
        "cell_features": (col_xs[2], row_ys[2]),
    }

    for m in MODULES:
        m.x, m.y = placements[m.key]


def draw_module(ax, m: Module):
    h = box_height(m)

    body = FancyBboxPatch(
        (m.x, m.y + HEADER_H), BOX_W, h - HEADER_H,
        boxstyle="round,pad=0.06", facecolor=m.body_color,
        edgecolor=m.header_color, linewidth=1.5,
    )
    ax.add_patch(body)

    header = FancyBboxPatch(
        (m.x, m.y), BOX_W, HEADER_H,
        boxstyle="round,pad=0.06", facecolor=m.header_color,
        edgecolor=m.header_color, linewidth=1.5,
    )
    ax.add_patch(header)

    ax.text(m.x + BOX_W / 2, m.y + HEADER_H / 2, m.label,
            ha="center", va="center", fontsize=HEADER_FONT,
            fontweight="bold", color="white", family="sans-serif")

    for i, ent in enumerate(m.entities):
        ey = m.y + HEADER_H + BOX_PAD + i * ROW_H + ROW_H * 0.45
        ax.text(m.x + BOX_PAD + 0.08, ey, ent,
                ha="left", va="center", fontsize=ENTITY_FONT,
                color="#222222", family="sans-serif")


def box_center(m: Module) -> tuple[float, float]:
    h = box_height(m)
    return m.x + BOX_W / 2, m.y + h / 2


def box_edge(m: Module, target_cx: float, target_cy: float) -> tuple[float, float]:
    """Return the point on the edge of m's box closest to (target_cx, target_cy)."""
    cx, cy = box_center(m)
    h = box_height(m)
    dx = target_cx - cx
    dy = target_cy - cy

    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        return cx, m.y + h

    candidates = []
    if dx != 0:
        for edge_x in [m.x, m.x + BOX_W]:
            t = (edge_x - cx) / dx
            if t > 0:
                iy = cy + t * dy
                if m.y <= iy <= m.y + h:
                    candidates.append((edge_x, iy))
    if dy != 0:
        for edge_y in [m.y, m.y + h]:
            t = (edge_y - cy) / dy
            if t > 0:
                ix = cx + t * dx
                if m.x <= ix <= m.x + BOX_W:
                    candidates.append((ix, edge_y))

    if not candidates:
        return cx, m.y + h

    return min(candidates, key=lambda p: (p[0] - target_cx)**2 + (p[1] - target_cy)**2)


def draw_edges(ax):
    seen_pairs: dict[tuple[str, str], int] = {}
    edge_idx: dict[tuple[str, str], int] = {}

    for edge in EDGES:
        pair = (min(edge.source, edge.target), max(edge.source, edge.target))
        if pair in seen_pairs:
            continue
        seen_pairs[pair] = 1
        idx = len(edge_idx)
        edge_idx[pair] = idx

        src = MODULE_MAP[edge.source]
        tgt = MODULE_MAP[edge.target]

        tcx, tcy = box_center(tgt)
        scx, scy = box_center(src)

        sx, sy = box_edge(src, tcx, tcy)
        tx, ty = box_edge(tgt, scx, scy)

        rad = 0.06 + (idx % 3) * 0.04

        ax.annotate(
            "", xy=(tx, ty), xytext=(sx, sy),
            arrowprops=dict(
                arrowstyle="-|>", color="#777777", lw=1.0,
                connectionstyle=f"arc3,rad={rad}",
                shrinkA=3, shrinkB=3,
            ),
        )

        pass


def draw_legend(ax):
    lx, ly = 0.5, 8.55
    ax.text(lx, ly, "Arrows indicate foreign-key references between modules",
            fontsize=7, fontstyle="italic", va="top",
            family="sans-serif", color="#666666")


def render_slide():
    assign_positions()

    fig, ax = plt.subplots(figsize=(16, 9))
    ax.set_xlim(0, 16)
    ax.set_ylim(9, 0)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor("white")

    draw_edges(ax)
    for m in MODULES:
        draw_module(ax, m)
    draw_legend(ax)

    out = DOCS_DIR / "erd_slide.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(out), dpi=300, bbox_inches="tight", pad_inches=0.2)
    plt.close(fig)
    print(f"Slide ERD rendered to {out}")


# ── Mermaid flowchart generation ───────────────────────────────────────

def generate_mermaid():
    lines = ["flowchart LR"]

    for m in MODULES:
        entity_list = "<br/>".join(m.entities)
        lines.append(f'    {m.key}["{m.label}<br/><i>{entity_list}</i>"]')

    lines.append("")

    seen: set[tuple[str, str]] = set()
    for edge in EDGES:
        pair = (min(edge.source, edge.target), max(edge.source, edge.target))
        if pair in seen:
            continue
        seen.add(pair)
        short_label = edge.label.replace("\n", ", ")
        lines.append(f'    {edge.source} -->|"{short_label}"| {edge.target}')

    mmd_src = "\n".join(lines) + "\n"

    mmd_path = DOCS_DIR / "erd_slide.mmd"
    mmd_path.write_text(mmd_src)
    print(f"Mermaid slide source written to {mmd_path}")

    css_rules = []
    for m in MODULES:
        css_rules.append(
            f'.node#{m.key} > .label-container '
            f'{{ fill: {m.body_color} !important; stroke: {m.header_color} !important; stroke-width: 2px !important; }}'
        )
        css_rules.append(
            f'[id*="{m.key}"] > rect, [id*="flowchart-{m.key}"] > rect '
            f'{{ fill: {m.body_color} !important; stroke: {m.header_color} !important; stroke-width: 2px !important; }}'
        )
        css_rules.append(
            f'[id*="flowchart-{m.key}"] > .label '
            f'{{ color: #222 !important; }}'
        )

    config = {"themeCSS": "\n".join(css_rules)}
    config_path = DOCS_DIR / "erd_slide_config.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    print(f"Mermaid slide config written to {config_path}")


def main():
    render_slide()
    generate_mermaid()


if __name__ == "__main__":
    main()
