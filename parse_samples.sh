#!/usr/bin/env bash
set -euo pipefail

# Convert all PDF files in samples/ to JSON using pdf-forms parse.
# Output JSON files are written alongside the PDFs (same directory).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SAMPLES_DIR="${SCRIPT_DIR}/samples"

if ! command -v pdf-forms &> /dev/null; then
    echo "Error: 'pdf-forms' command not found. Is the package installed?" >&2
    exit 1
fi

for pdf in "${SAMPLES_DIR}"/*.pdf; do
    if [ -f "${pdf}" ]; then
        echo "Parsing: ${pdf}"
        pdf-forms parse "${pdf}"
    fi
done

echo "Done."
