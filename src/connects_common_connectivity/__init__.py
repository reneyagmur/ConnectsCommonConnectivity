"""Connects Common Connectivity package.


"""

from pathlib import Path

__version__ = "0.1.0"

# Schema path: when installed in editable mode, schemas live at repo root / schemas /
def get_schema_path(schema_name: str = "connectivity_schema.yaml") -> str:
    """Return path to a schema YAML file (default: connectivity_schema.yaml)."""
    # Package layout: src/connects_common_connectivity/__init__.py -> repo root is parent.parent.parent
    repo_root = Path(__file__).resolve().parent.parent.parent
    path = repo_root / "schemas" / schema_name
    if not path.exists():
        # Fallback for non-editable installs or different layouts
        path = Path(__file__).resolve().parent.parent / "schemas" / schema_name
    return str(path)


def generate_pydantic_models(schema_name: str | None = None) -> dict:
    """Return a dict of schema class/enum name -> Pydantic class.

    This package uses statically generated models (models.py from gen-pydantic).
    The schema_name argument is accepted for API compatibility but the static
    models are always returned.
    """
    from . import models

    # Export all public LinkML-generated classes and enums (exclude helpers)
    exclude = {"ConfiguredBaseModel", "LinkMLMeta", "linkml_meta"}
    return {
        name: getattr(models, name)
        for name in dir(models)
        if name not in exclude
        and not name.startswith("_")
        and isinstance(getattr(models, name), type)
    }

