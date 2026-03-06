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

Run `npm install` from the repo root once (creates `node_modules/`; `.npmrc` skips Puppeteer Chrome download, uses system Chrome). Then:

```bash
./node_modules/.bin/mmdc -i docs/erd.mmd -o docs/erd_mermaid.png -t default -b white -w 6000 -H 4000 -s 3 -c docs/mermaid-config.json
./node_modules/.bin/mmdc -i docs/erd.mmd -o docs/erd_mermaid.svg -t default -b white -w 6000 -H 4000 -s 3 -c docs/mermaid-config.json
```

Or use a global install (`npm install -g @mermaid-js/mermaid-cli`) and run `mmdc` directly.

**4. Regenerate slide ERD** (`erd_slide.png`, `erd_slide.mmd`):

```bash
MPLCONFIGDIR=/tmp/mpl_config .venv/bin/python scripts/render_erd_slide.py
./node_modules/.bin/mmdc -i docs/erd_slide.mmd -o docs/erd_slide_mermaid.png -t default -b white -w 2400 -H 1350 -s 2 -c docs/erd_slide_config.json
./node_modules/.bin/mmdc -i docs/erd_slide.mmd -o docs/erd_slide_mermaid.svg -t default -b white -w 2400 -H 1350 -s 2 -c docs/erd_slide_config.json
```

**5. Regenerate erd_updated** (after schema changes, full pipeline from scratch):

```bash
.venv/bin/python scripts/generate_erd.py -o erd_updated
MPLCONFIGDIR=/tmp/mpl_config .venv/bin/python scripts/render_erd.py -o erd_updated.png
./scripts/render_erd_updated_mermaid.sh
```

### Dependencies

- **Python** (`.venv`): `pyyaml`, `matplotlib` -- already in the virtual environment.
- **Node.js** (for mermaid-cli): `brew install node` + `npm install` from repo root. `package.json` is committed; `node_modules/` is gitignored.
