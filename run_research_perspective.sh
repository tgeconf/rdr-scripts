#!/usr/bin/env bash
set -euo pipefail

# Resolve repository root
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Allow overriding the Python interpreter
PYTHON_BIN="${PYTHON_BIN:-python}"

# Default arguments with environment-variable overrides
RUN_DATE="${RUN_DATE:-$(date +%Y-%m-%d)}"
DATASET_DIR="$ROOT_DIR/dataset/$RUN_DATE"
mkdir -p "$DATASET_DIR"

CLASSIFICATION_PATH="${CLASSIFICATION_PATH:-"$DATASET_DIR/arxiv_area_classification.json"}"
PAPER_DATASET_PATH="${PAPER_DATASET_PATH:-"$DATASET_DIR/arxiv_web.json"}"
OUTPUT_PATH="${OUTPUT_PATH:-"$DATASET_DIR/arxiv_research_perspective.json"}"
REQUEST_INTERVAL="${REQUEST_INTERVAL:-1.0}"

declare -a SCRIPT_ARGS=(
  --classification "$CLASSIFICATION_PATH"
  --papers "$PAPER_DATASET_PATH"
  --output "$OUTPUT_PATH"
  --interval "$REQUEST_INTERVAL"
)

exec "$PYTHON_BIN" -B -m arxiv_analyzer.research_perspective "${SCRIPT_ARGS[@]}" "$@"
