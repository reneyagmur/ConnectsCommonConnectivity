#!/usr/bin/env python3
"""Parse LinkML YAML schemas and emit a Mermaid erDiagram to docs/erd.md.

Also generates:
  - docs/erd.mmd          (raw Mermaid source for mermaid-cli)
  - docs/mermaid-config.json (custom theme CSS for entity color-coding)
"""

from __future__ import annotations

import json
import pathlib
import yaml

SCHEMA_DIR = pathlib.Path(__file__).resolve().parent.parent / "schemas"
DOCS_DIR = pathlib.Path(__file__).resolve().parent.parent / "docs"

MIXIN_CLASSES = {"ProjectScoped"}

SCHEMA_GROUPS = {
    "core":          {"DataSet", "DataItem", "DataItemDataSetAssociation", "SpatialLocation"},
    "zarr":          {"ZarrArray", "ZarrDataset", "ParquetDataset"},
    "brain_region":  {"BrainRegion", "BrainRegionAssociation"},
    "clustering":    {"AlgorithmRun", "Taxonomy", "Cluster", "ClusterMembership", "HierachyCategory"},
    "projection":    {"ProjectionMeasurementMatrix"},
    "cell_cell":     {"CellCellConnectivityLong", "CellCellMeasurementMatrix"},
    "cell_gene":     {"CellGeneData", "BarcodingExperimentMetadata", "GeneMetadata", "CellMetadata"},
    "cell_features": {"CellFeatureSet", "CellFeatureDefinition", "CellFeatureMatrix", "CellFeatureMeasurement"},
    "single_cell":   {"SingleCellReconstruction"},
    "mappings":      {"MappingSet", "CellToCellMapping", "CellToClusterMapping", "ClusterToClusterMapping"},
}

GROUP_COLORS = {
    "core":          {"fill": "#D6E4F0", "stroke": "#4472C4", "label": "Core (DataSet, DataItem, ...)"},
    "zarr":          {"fill": "#E2EFDA", "stroke": "#548235", "label": "Storage (Zarr, Parquet)"},
    "brain_region":  {"fill": "#FFF2CC", "stroke": "#BF8F00", "label": "Brain Region"},
    "clustering":    {"fill": "#E2D1F0", "stroke": "#7030A0", "label": "Clustering"},
    "projection":    {"fill": "#FCE4D6", "stroke": "#C55A11", "label": "Projection"},
    "cell_cell":     {"fill": "#F4CCCC", "stroke": "#C00000", "label": "Cell-Cell Connectivity"},
    "cell_gene":     {"fill": "#DAEEF3", "stroke": "#0070C0", "label": "Cell-Gene Expression"},
    "cell_features": {"fill": "#D9F2E6", "stroke": "#00B050", "label": "Cell Features"},
    "single_cell":   {"fill": "#E0E0E0", "stroke": "#606060", "label": "Single Cell"},
    "mappings":      {"fill": "#FBE5D6", "stroke": "#9C5700", "label": "Mappings"},
}


def get_group(class_name: str) -> str:
    for group, members in SCHEMA_GROUPS.items():
        if class_name in members:
            return group
    return "core"


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


def mermaid_type(range_val: str | None, all_classes: set[str], enums: set[str]) -> str:
    if range_val is None:
        return "string"
    return range_val


def build_erd(schemas: list[dict]) -> str:
    enums = collect_enums(schemas)
    classes = collect_classes(schemas)
    global_slots = collect_global_slots(schemas)
    class_names = set(classes.keys())

    lines: list[str] = ["erDiagram"]
    relationships: list[str] = []
    entity_blocks: list[str] = []

    for cls_name, cls_defn in sorted(classes.items()):
        slot_names = list(cls_defn.get("slots", []))

        for mixin in cls_defn.get("mixins", []):
            if mixin in MIXIN_CLASSES:
                for schema in schemas:
                    if mixin in schema.get("classes", {}):
                        slot_names.extend(schema["classes"][mixin].get("slots", []))
                        break

        attrs: list[str] = []
        for slot_name in slot_names:
            resolved = resolve_slot(slot_name, cls_defn, global_slots)
            range_val = resolved.get("range")
            is_identifier = resolved.get("identifier", False)
            is_required = resolved.get("required", False)
            is_multivalued = resolved.get("multivalued", False)

            if range_val in class_names:
                left_card = "||" if is_required else "|o"
                right_card = "}o" if is_multivalued else "||"
                relationships.append(
                    f'    {cls_name} {left_card}--{right_card} {range_val} : "{slot_name}"'
                )
                type_str = range_val
                tag = "PK,FK" if is_identifier else "FK"
                attrs.append(f"        {type_str} {slot_name} {tag}")
            else:
                type_str = mermaid_type(range_val, class_names, enums)
                if is_identifier:
                    attrs.append(f"        {type_str} {slot_name} PK")
                else:
                    attrs.append(f"        {type_str} {slot_name}")

        block = f"    {cls_name} {{\n" + "\n".join(attrs) + f"\n    }}"
        entity_blocks.append(block)

    lines.append("")
    for block in entity_blocks:
        lines.append(block)
        lines.append("")

    seen_rels: set[str] = set()
    for rel in relationships:
        if rel not in seen_rels:
            lines.append(rel)
            seen_rels.add(rel)

    return "\n".join(lines) + "\n"


def build_css(classes: dict[str, dict]) -> str:
    """Generate CSS rules that color-code each entity by its schema group.

    Mermaid erDiagram renders each entity as an SVG <g> with
    id="entity-{Name}-{index}".  The first child <g> contains two <path>
    elements: body-fill (1st) and border-stroke (2nd).
    """
    sorted_names = sorted(classes.keys())
    name_to_idx = {name: idx for idx, name in enumerate(sorted_names)}

    css_rules: list[str] = []
    for name, idx in name_to_idx.items():
        group = get_group(name)
        colors = GROUP_COLORS[group]
        eid = f"entity-{name}-{idx}"

        css_rules.append(
            f'[id^="{eid}"] > g:first-child > path:first-child '
            f'{{ fill: {colors["fill"]} !important; }}'
        )
        css_rules.append(
            f'[id^="{eid}"] > g:first-child > path:nth-child(2) '
            f'{{ stroke: {colors["stroke"]} !important; stroke-width: 2px !important; }}'
        )

    return "\n".join(css_rules)


def build_mermaid_config(classes: dict[str, dict]) -> dict:
    css = build_css(classes)
    return {"themeCSS": css}


ARROW_LEGEND = """\
## Relationship Notation (Crow's Foot)

| Symbol | Meaning |
|--------|---------|
| `\\|\\|` | Exactly one (mandatory) |
| `\\|o` | Zero or one (optional) |
| `}o` | Zero or more |
| `}\\|` | One or more |

Reading example: `A ||--}o B : "items"` means *each A has zero-or-more B* via the `items` field, and *each B belongs to exactly one A*.
"""


def build_color_legend() -> str:
    lines = ["## Schema Module Colors", "", "| Color | Schema Module | Entities |", "|-------|---------------|----------|"]
    for group, colors in GROUP_COLORS.items():
        entities = ", ".join(f"`{e}`" for e in sorted(SCHEMA_GROUPS[group]))
        swatch = f'![{group}](https://via.placeholder.com/16/{colors["stroke"].lstrip("#")}/{colors["stroke"].lstrip("#")}.png)'
        lines.append(f'| {swatch} **{colors["label"]}** | `{group}` | {entities} |')
    return "\n".join(lines) + "\n"


def main() -> None:
    schemas = load_all_schemas(SCHEMA_DIR)
    classes = collect_classes(schemas)
    mermaid_src = build_erd(schemas)

    color_legend = build_color_legend()
    md_content = (
        "# Connectivity Schema - Entity Relationship Diagram\n\n"
        f"{ARROW_LEGEND}\n"
        f"{color_legend}\n"
        "## Diagram\n\n"
        f"```mermaid\n{mermaid_src}```\n"
    )

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "erd.md").write_text(md_content)
    print(f"ERD written to {DOCS_DIR / 'erd.md'}")

    (DOCS_DIR / "erd.mmd").write_text(mermaid_src)
    print(f"Mermaid source written to {DOCS_DIR / 'erd.mmd'}")

    config = build_mermaid_config(classes)
    config_path = DOCS_DIR / "mermaid-config.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    print(f"Mermaid config written to {config_path}")


if __name__ == "__main__":
    main()
