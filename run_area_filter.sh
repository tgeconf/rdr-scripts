#!/usr/bin/env bash
set -euo pipefail

# Resolve repository root (directory containing this script)
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Allow overriding the Python interpreter by exporting PYTHON_BIN
PYTHON_BIN="${PYTHON_BIN:-python}"

# Default parameters, overridable via env vars
RUN_DATE="${RUN_DATE:-$(date +%Y-%m-%d)}"
DATASET_DIR="$ROOT_DIR/dataset/$RUN_DATE"
mkdir -p "$DATASET_DIR"

DATASET_PATH="${DATASET_PATH:-"$DATASET_DIR/arxiv_web.json"}"
OUTPUT_PATH="${OUTPUT_PATH:-"$DATASET_DIR/arxiv_area_classification.json"}"
REQUEST_INTERVAL="${REQUEST_INTERVAL:-1.0}"
RESUME_RUN="${RESUME_RUN:-1}"

declare -a SCRIPT_ARGS=(
  --dataset "$DATASET_PATH"
  --output "$OUTPUT_PATH"
  --model deepseek-reasoner
  --temperature 0
  --interval "$REQUEST_INTERVAL"
)

if [[ "$RESUME_RUN" == "0" || "$RESUME_RUN" == "false" ]]; then
  SCRIPT_ARGS+=(--no-resume)
fi

exec "$PYTHON_BIN" -B -m arxiv_analyzer.area_filter "${SCRIPT_ARGS[@]}" "$@"
