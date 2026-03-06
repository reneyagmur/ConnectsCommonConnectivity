#!/usr/bin/env bash
# Render erd_updated.mmd to PNG and SVG via mermaid-cli.
# Uses npx (no global install needed). Uses system Chrome if mmdc not found.
#
# Usage: ./scripts/render_erd_updated_mermaid.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCS_DIR="$(cd "$SCRIPT_DIR/../docs" && pwd)"

if command -v mmdc &>/dev/null; then
  mmdc -i "$DOCS_DIR/erd_updated.mmd" -o "$DOCS_DIR/erd_updated_mermaid.png" \
    -t default -b white -w 6000 -H 4000 -s 3 -c "$DOCS_DIR/mermaid-config.json"
  mmdc -i "$DOCS_DIR/erd_updated.mmd" -o "$DOCS_DIR/erd_updated_mermaid.svg" \
    -t default -b white -w 6000 -H 4000 -s 3 -c "$DOCS_DIR/mermaid-config.json"
else
  # Use npx with system Chrome (avoids Puppeteer Chrome download)
  export PUPPETEER_EXECUTABLE_PATH="${PUPPETEER_EXECUTABLE_PATH:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
  npx --yes @mermaid-js/mermaid-cli -i "$DOCS_DIR/erd_updated.mmd" -o "$DOCS_DIR/erd_updated_mermaid.png" \
    -t default -b white -w 6000 -H 4000 -s 3 -c "$DOCS_DIR/mermaid-config.json"
  npx --yes @mermaid-js/mermaid-cli -i "$DOCS_DIR/erd_updated.mmd" -o "$DOCS_DIR/erd_updated_mermaid.svg" \
    -t default -b white -w 6000 -H 4000 -s 3 -c "$DOCS_DIR/mermaid-config.json"
fi

echo "Rendered to docs/erd_updated_mermaid.png and docs/erd_updated_mermaid.svg"
