#!/usr/bin/env python3
"""Render the connectivity ERD as a PNG using matplotlib.

Parses the same YAML schemas as generate_erd.py and draws a styled ERD image
with colored entity boxes, PK/FK annotations, and relationship lines.
"""

from __future__ import annotations

import math
import pathlib
from dataclasses import dataclass, field

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import yaml

SCHEMA_DIR = pathlib.Path(__file__).resolve().parent.parent / "schemas"
OUTPUT_FILE = pathlib.Path(__file__).resolve().parent.parent / "docs" / "erd.png"

PRIMITIVE_TYPES = {
    "string", "integer", "float", "boolean", "double", "decimal",
    "date", "datetime", "time", "uri", "uriorcurie", "ncname",
}
MIXIN_CLASSES = {"ProjectScoped"}

SCHEMA_GROUPS = {
    "core": {"DataSet", "DataItem", "DataItemDataSetAssociation", "SpatialLocation"},
    "zarr": {"ZarrArray", "ZarrDataset", "ParquetDataset"},
    "brain_region": {"BrainRegion", "BrainRegionAssociation"},
    "clustering": {"AlgorithmRun", "Taxonomy", "Cluster", "ClusterMembership", "HierachyCategory"},
    "projection": {"ProjectionMeasurementMatrix"},
    "cell_cell": {"CellCellConnectivityLong", "CellCellMeasurementMatrix"},
    "cell_gene": {"CellGeneData", "BarcodingExperimentMetadata", "GeneMetadata", "CellMetadata"},
    "cell_features": {"CellFeatureSet", "CellFeatureDefinition", "CellFeatureMatrix", "CellFeatureMeasurement"},
    "single_cell": {"SingleCellReconstruction"},
    "mappings": {"MappingSet", "CellToCellMapping", "CellToClusterMapping", "ClusterToClusterMapping"},
}

GROUP_COLORS = {
    "core":          {"header": "#4472C4", "body": "#D6E4F0", "header_text": "white"},
    "zarr":          {"header": "#548235", "body": "#E2EFDA", "header_text": "white"},
    "brain_region":  {"header": "#BF8F00", "body": "#FFF2CC", "header_text": "white"},
    "clustering":    {"header": "#7030A0", "body": "#E2D1F0", "header_text": "white"},
    "projection":    {"header": "#C55A11", "body": "#FCE4D6", "header_text": "white"},
    "cell_cell":     {"header": "#C00000", "body": "#F4CCCC", "header_text": "white"},
    "cell_gene":     {"header": "#0070C0", "body": "#DAEEF3", "header_text": "white"},
    "cell_features": {"header": "#00B050", "body": "#D9F2E6", "header_text": "white"},
    "single_cell":   {"header": "#808080", "body": "#E0E0E0", "header_text": "white"},
    "mappings":      {"header": "#9C5700", "body": "#FBE5D6", "header_text": "white"},
}


def get_group(class_name: str) -> str:
    for group, members in SCHEMA_GROUPS.items():
        if class_name in members:
            return group
    return "core"


@dataclass
class SlotInfo:
    name: str
    type_str: str
    is_pk: bool = False
    is_fk: bool = False


@dataclass
class EntityInfo:
    name: str
    slots: list[SlotInfo] = field(default_factory=list)
    group: str = "core"


@dataclass
class RelationshipInfo:
    source: str
    target: str
    label: str
    source_card: str  # "1" or "0..1"
    target_card: str  # "1", "*", "0..*"


def load_all_schemas(schema_dir: pathlib.Path) -> list[dict]:
    schemas = []
    for path in sorted(schema_dir.glob("*.yaml")):
        with open(path) as f:
            schemas.append(yaml.safe_load(f))
    return schemas


def collect_enums(schemas: list[dict]) -> set[str]:
    enums = set()
    for schema in schemas:
        for name in schema.get("enums", {}):
            enums.add(name)
    return enums


def collect_classes(schemas: list[dict]) -> dict[str, dict]:
    classes: dict[str, dict] = {}
    for schema in schemas:
        for name, defn in schema.get("classes", {}).items():
            if name not in MIXIN_CLASSES:
                classes[name] = defn
    return classes


def collect_global_slots(schemas: list[dict]) -> dict[str, dict]:
    slots: dict[str, dict] = {}
    for schema in schemas:
        for name, defn in schema.get("slots", {}).items():
            if name not in slots:
                slots[name] = defn or {}
            else:
                slots[name].update(defn or {})
    return slots


def resolve_slot(slot_name: str, class_defn: dict, global_slots: dict[str, dict]) -> dict:
    base = dict(global_slots.get(slot_name, {}))
    overrides = class_defn.get("slot_usage", {}).get(slot_name, {})
    base.update(overrides)
    return base


def build_entities_and_relationships(
    schemas: list[dict],
) -> tuple[list[EntityInfo], list[RelationshipInfo]]:
    enums = collect_enums(schemas)
    classes = collect_classes(schemas)
    global_slots = collect_global_slots(schemas)
    class_names = set(classes.keys())

    entities: list[EntityInfo] = []
    relationships: list[RelationshipInfo] = []
    seen_rels: set[tuple] = set()

    for cls_name, cls_defn in sorted(classes.items()):
        entity = EntityInfo(name=cls_name, group=get_group(cls_name))
        slot_names = list(cls_defn.get("slots", []))

        for mixin in cls_defn.get("mixins", []):
            if mixin in MIXIN_CLASSES:
                for schema in schemas:
                    if mixin in schema.get("classes", {}):
                        slot_names.extend(schema["classes"][mixin].get("slots", []))
                        break

        for slot_name in slot_names:
            resolved = resolve_slot(slot_name, cls_defn, global_slots)
            range_val = resolved.get("range")
            is_identifier = resolved.get("identifier", False)
            is_required = resolved.get("required", False)
            is_multivalued = resolved.get("multivalued", False)
            is_fk = range_val in class_names

            if is_fk:
                type_str = range_val
            elif range_val in enums:
                type_str = range_val
            elif range_val:
                type_str = range_val
            else:
                type_str = "string"

            tag_pk = is_identifier
            tag_fk = is_fk and not is_identifier
            if is_identifier and is_fk:
                tag_pk = True
                tag_fk = True

            entity.slots.append(SlotInfo(
                name=slot_name, type_str=type_str,
                is_pk=tag_pk, is_fk=tag_fk,
            ))

            if is_fk:
                src_card = "1" if is_required else "0..1"
                tgt_card = "0..*" if is_multivalued else "1"
                rel_key = (cls_name, range_val, slot_name)
                if rel_key not in seen_rels:
                    seen_rels.add(rel_key)
                    relationships.append(RelationshipInfo(
                        source=cls_name, target=range_val,
                        label=slot_name,
                        source_card=src_card, target_card=tgt_card,
                    ))

        entities.append(entity)

    return entities, relationships


# ── Drawing constants ──────────────────────────────────────────────────

CHAR_WIDTH = 0.085
ROW_HEIGHT = 0.28
HEADER_HEIGHT = 0.38
TAG_COL_WIDTH = 0.55
PADDING_X = 0.2
PADDING_Y = 0.15
ENTITY_GAP_X = 0.6
ENTITY_GAP_Y = 0.5
FONT_SIZE = 7
HEADER_FONT_SIZE = 8


def entity_width(entity: EntityInfo) -> float:
    max_text = max(
        (len(s.type_str) + len(s.name) + 2 for s in entity.slots),
        default=10,
    )
    name_w = len(entity.name) * CHAR_WIDTH * (HEADER_FONT_SIZE / FONT_SIZE)
    body_w = TAG_COL_WIDTH + max_text * CHAR_WIDTH + PADDING_X
    return max(name_w + 2 * PADDING_X, body_w)


def entity_height(entity: EntityInfo) -> float:
    return HEADER_HEIGHT + len(entity.slots) * ROW_HEIGHT + PADDING_Y


def layout_entities(entities: list[EntityInfo]) -> dict[str, tuple[float, float, float, float]]:
    """Return {name: (x, y, w, h)} using a grid layout grouped by schema module."""

    group_order = [
        "core", "zarr", "brain_region", "clustering",
        "projection", "cell_cell", "cell_gene",
        "cell_features", "single_cell", "mappings",
    ]

    grouped: dict[str, list[EntityInfo]] = {g: [] for g in group_order}
    for e in entities:
        grouped.setdefault(e.group, []).append(e)

    columns: list[list[EntityInfo]] = []
    col: list[EntityInfo] = []
    col_height = 0.0
    MAX_COL_HEIGHT = 22.0

    for g in group_order:
        for e in grouped[g]:
            h = entity_height(e)
            if col and col_height + h + ENTITY_GAP_Y > MAX_COL_HEIGHT:
                columns.append(col)
                col = []
                col_height = 0.0
            col.append(e)
            col_height += h + ENTITY_GAP_Y
    if col:
        columns.append(col)

    positions: dict[str, tuple[float, float, float, float]] = {}
    x_offset = 0.5

    for col_entities in columns:
        col_width = max(entity_width(e) for e in col_entities)
        y_offset = 0.5
        for e in col_entities:
            w = col_width
            h = entity_height(e)
            positions[e.name] = (x_offset, y_offset, w, h)
            y_offset += h + ENTITY_GAP_Y
        x_offset += col_width + ENTITY_GAP_X

    return positions


def draw_entity(ax, entity: EntityInfo, x: float, y: float, w: float, h: float):
    colors = GROUP_COLORS.get(entity.group, GROUP_COLORS["core"])

    header_rect = FancyBboxPatch(
        (x, y), w, HEADER_HEIGHT,
        boxstyle="round,pad=0.02",
        facecolor=colors["header"], edgecolor="#333333", linewidth=0.8,
    )
    ax.add_patch(header_rect)
    ax.text(
        x + w / 2, y + HEADER_HEIGHT / 2,
        entity.name, ha="center", va="center",
        fontsize=HEADER_FONT_SIZE, fontweight="bold", color=colors["header_text"],
        family="sans-serif",
    )

    body_rect = FancyBboxPatch(
        (x, y + HEADER_HEIGHT), w, h - HEADER_HEIGHT,
        boxstyle="round,pad=0.02",
        facecolor=colors["body"], edgecolor="#333333", linewidth=0.8,
    )
    ax.add_patch(body_rect)

    tag_x = x + 0.08
    name_x = x + TAG_COL_WIDTH
    row_y = y + HEADER_HEIGHT + 0.08

    for slot in entity.slots:
        tag = ""
        if slot.is_pk and slot.is_fk:
            tag = "PK,FK"
        elif slot.is_pk:
            tag = "PK"
        elif slot.is_fk:
            tag = "FK"

        if tag:
            ax.text(
                tag_x, row_y + ROW_HEIGHT * 0.4,
                tag, ha="left", va="center",
                fontsize=FONT_SIZE - 1, fontweight="bold", color="#444444",
                family="sans-serif",
            )

        style = "italic" if slot.is_fk else "normal"
        weight = "bold" if slot.is_pk else "normal"
        display = f"{slot.name}"

        ax.text(
            name_x, row_y + ROW_HEIGHT * 0.4,
            display, ha="left", va="center",
            fontsize=FONT_SIZE, fontstyle=style, fontweight=weight,
            color="#222222", family="sans-serif",
        )

        row_y += ROW_HEIGHT

    ax.plot([x + TAG_COL_WIDTH - 0.08, x + TAG_COL_WIDTH - 0.08],
            [y + HEADER_HEIGHT, y + h], color="#AAAAAA", linewidth=0.5)


def draw_relationships(ax, relationships: list[RelationshipInfo],
                       positions: dict[str, tuple[float, float, float, float]]):
    for rel in relationships:
        if rel.source not in positions or rel.target not in positions:
            continue

        sx, sy, sw, sh = positions[rel.source]
        tx, ty, tw, th = positions[rel.target]

        scx, scy = sx + sw / 2, sy + sh / 2
        tcx, tcy = tx + tw / 2, ty + th / 2

        if rel.source == rel.target:
            start_x = sx + sw
            start_y = scy - 0.3
            end_x = sx + sw
            end_y = scy + 0.3
            loop_offset = 0.6
            ax.annotate("", xy=(end_x, end_y),
                        xytext=(end_x + loop_offset, end_y),
                        arrowprops=dict(arrowstyle="-|>", color="#888888", lw=0.7))
            ax.plot([start_x, start_x + loop_offset], [start_y, start_y],
                    color="#888888", lw=0.7)
            ax.plot([start_x + loop_offset, start_x + loop_offset],
                    [start_y, end_y], color="#888888", lw=0.7)
            continue

        dx = tcx - scx
        dy = tcy - scy

        if abs(dx) > abs(dy):
            if dx > 0:
                start_x, start_y = sx + sw, scy
                end_x, end_y = tx, tcy
            else:
                start_x, start_y = sx, scy
                end_x, end_y = tx + tw, tcy
        else:
            if dy > 0:
                start_x, start_y = scx, sy + sh
                end_x, end_y = tcx, ty
            else:
                start_x, start_y = scx, sy
                end_x, end_y = tcx, ty + th

        ax.annotate(
            "", xy=(end_x, end_y), xytext=(start_x, start_y),
            arrowprops=dict(arrowstyle="-", color="#888888", lw=0.7,
                            connectionstyle="arc3,rad=0.05"),
        )


def render_erd(entities: list[EntityInfo], relationships: list[RelationshipInfo],
               output_path: pathlib.Path):
    positions = layout_entities(entities)

    all_x = [x + w for x, y, w, h in positions.values()]
    all_y = [y + h for x, y, w, h in positions.values()]
    fig_w = max(all_x) + 1.0
    fig_h = max(all_y) + 1.0

    fig, ax = plt.subplots(1, 1, figsize=(fig_w, fig_h))
    ax.set_xlim(0, fig_w)
    ax.set_ylim(fig_h, 0)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor("white")

    draw_relationships(ax, relationships, positions)

    entity_map = {e.name: e for e in entities}
    for name, (x, y, w, h) in positions.items():
        draw_entity(ax, entity_map[name], x, y, w, h)

    group_order = [
        "core", "zarr", "brain_region", "clustering", "projection",
        "cell_cell", "cell_gene", "cell_features", "single_cell", "mappings",
    ]
    GROUP_LABELS = {
        "core": "Core", "zarr": "Storage", "brain_region": "Brain Region",
        "clustering": "Clustering", "projection": "Projection",
        "cell_cell": "Cell-Cell", "cell_gene": "Cell-Gene",
        "cell_features": "Cell Features", "single_cell": "Single Cell",
        "mappings": "Mappings",
    }
    legend_patches = []
    present_groups = {e.group for e in entities}
    for g in group_order:
        if g in present_groups:
            c = GROUP_COLORS[g]
            legend_patches.append(mpatches.Patch(
                facecolor=c["body"], edgecolor=c["header"], linewidth=1.5,
                label=GROUP_LABELS[g],
            ))

    color_legend = ax.legend(
        handles=legend_patches, loc="upper right",
        fontsize=6, framealpha=0.95, title="Schema Module",
        title_fontsize=7, borderpad=0.8, labelspacing=0.4,
    )
    ax.add_artist(color_legend)

    arrow_legend_x = 0.6
    arrow_legend_y = fig_h - 0.3
    arrow_items = [
        ("||--||", "exactly one  to  exactly one (required)"),
        ("|o--||", "zero-or-one  to  exactly one (optional FK)"),
        ("|o--}o", "zero-or-one  to  zero-or-more (optional, multivalued)"),
        ("||--}o", "exactly one  to  zero-or-more (required, multivalued)"),
    ]
    ax.text(arrow_legend_x, arrow_legend_y, "Relationship Notation",
            fontsize=7, fontweight="bold", va="top", family="sans-serif")
    for i, (sym, desc) in enumerate(arrow_items):
        y = arrow_legend_y + 0.32 + i * 0.28
        ax.text(arrow_legend_x + 0.05, y, sym, fontsize=6, fontweight="bold",
                va="top", family="monospace", color="#555555")
        ax.text(arrow_legend_x + 1.0, y, desc, fontsize=5.5,
                va="top", family="sans-serif", color="#333333")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=200, bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)
    print(f"ERD rendered to {output_path}")


def main():
    schemas = load_all_schemas(SCHEMA_DIR)
    entities, relationships = build_entities_and_relationships(schemas)
    render_erd(entities, relationships, OUTPUT_FILE)


if __name__ == "__main__":
    main()
