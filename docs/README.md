# Documentation

## Entity Relationship Diagram (ERD)

The ERD visualizes all classes, attributes, and relationships defined in the LinkML YAML schemas under `schemas/`.

### Generated files

| File | Description |
|---|---|
| `erd.md` | Mermaid source with arrow-type and color legends (renders in GitHub / Cursor Markdown preview) |
| `erd.mmd` | Raw Mermaid source file (input for mermaid-cli) |
| `mermaid-config.json` | Mermaid theme CSS that color-codes entities by schema module |
| `erd.png` | Color-coded PNG rendered via matplotlib (includes both legends) |
| `erd_mermaid.png` | Color-coded PNG rendered via mermaid-cli |
| `erd_mermaid.svg` | Color-coded SVG rendered via mermaid-cli (recommended -- zoom/pan in browser) |

### How to regenerate

Both scripts live in `scripts/` and use the `.venv` Python environment.

**1. Regenerate Mermaid source and config** (`erd.md`, `erd.mmd`, `mermaid-config.json`):

```bash
.venv/bin/python scripts/generate_erd.py
```

**2. Regenerate matplotlib PNG** (`erd.png`):

```bash
MPLCONFIGDIR=/tmp/mpl_config .venv/bin/python scripts/render_erd.py
```

**3. Regenerate mermaid-cli PNG/SVG** (`erd_mermaid.png`, `erd_mermaid.svg`):

Requires Node.js and `@mermaid-js/mermaid-cli` installed globally:

```bash
brew install node                          # if not already installed
npm install -g @mermaid-js/mermaid-cli     # one-time global install
```

Then render:

```bash
mmdc -i docs/erd.mmd -o docs/erd_mermaid.png -t default -b white -w 6000 -H 4000 -s 3 -c docs/mermaid-config.json
mmdc -i docs/erd.mmd -o docs/erd_mermaid.svg -t default -b white -w 6000 -H 4000 -s 3 -c docs/mermaid-config.json
```

The `-c docs/mermaid-config.json` flag applies per-entity CSS that color-codes each table by its schema module.

**4. Regenerate slide ERD** (`erd_slide.png`, `erd_slide.mmd`):

```bash
MPLCONFIGDIR=/tmp/mpl_config .venv/bin/python scripts/render_erd_slide.py
mmdc -i docs/erd_slide.mmd -o docs/erd_slide_mermaid.png -t default -b white -w 2400 -H 1350 -s 2 -c docs/erd_slide_config.json
mmdc -i docs/erd_slide.mmd -o docs/erd_slide_mermaid.svg -t default -b white -w 2400 -H 1350 -s 2 -c docs/erd_slide_config.json
```

### Dependencies

- **Python** (`.venv`): `pyyaml`, `matplotlib` -- already in the virtual environment.
- **Node.js** (optional, for mermaid-cli renders): `brew install node` + `npm install -g @mermaid-js/mermaid-cli`. Not vendored in this repo.
