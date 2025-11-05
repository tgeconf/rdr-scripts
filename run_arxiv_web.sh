#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"

RUN_DATE="${RUN_DATE:-$(date +%Y-%m-%d)}"
DATASET_RELATIVE_PATH="${RUN_DATE}/arxiv_web.json"
DATASET_DIR="$ROOT_DIR/dataset/$RUN_DATE"

mkdir -p "$DATASET_DIR"

declare -a SCRIPT_ARGS=(
  --output "$DATASET_RELATIVE_PATH"
)

if [[ -n "${ARXIV_CATEGORIES:-}" ]]; then
  read -r -a _cats <<<"$ARXIV_CATEGORIES"
  SCRIPT_ARGS+=(--categories "${_cats[@]}")
fi

if [[ -n "${WEB_MAX_WORKERS:-}" ]]; then
  SCRIPT_ARGS+=(--max-workers "$WEB_MAX_WORKERS")
fi

if [[ -n "${WEB_DAYS_BACK:-}" ]]; then
  SCRIPT_ARGS+=(--days-back "$WEB_DAYS_BACK")
fi

exec "$PYTHON_BIN" -B -m arxiv_analyzer.arxiv_web "${SCRIPT_ARGS[@]}" "$@"
