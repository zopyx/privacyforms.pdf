#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SAMPLES_DIR="${SCRIPT_DIR}/samples"

echo "Converting PDF forms in ${SAMPLES_DIR} ..."

for pdf in "${SAMPLES_DIR}"/*.pdf; do
    [ -e "$pdf" ] || continue
    [ -L "$pdf" ] && continue
    echo ""
    echo "Processing: $(basename "$pdf")"
    uv run python "${SCRIPT_DIR}/pdf_parser.py" "$pdf"
done

echo ""
echo "All conversions complete."
