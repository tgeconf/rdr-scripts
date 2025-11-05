#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# Daily arXiv processing pipeline
# -----------------------------------------------------------------------------
# Execution order:
#   1. arxiv_analyzer.arxiv_web
#   2. arxiv_analyzer.area_filter
#   3. arxiv_analyzer.research_perspective
#   4. arxiv_analyzer.arxiv_clustering
#
# Usage:
#   ./run_daily_pipeline.sh                 # uses today's date (YYYY-MM-DD)
#   ./run_daily_pipeline.sh 2024-05-08      # use a specific date
#
# Environment overrides:
#   PYTHON_BIN          - Python interpreter to use (default: python)
#   ARXIV_CATEGORIES    - Space separated list passed to web crawler
#   WEB_MAX_WORKERS     - Override --max-workers for crawler
#   WEB_DAYS_BACK       - Override --days-back for crawler
#   AREA_REQUEST_INTERVAL - Override --interval for area filter
#   AREA_NO_RESUME      - If set to 1 or true, add --no-resume to area filter
#   PERSPECTIVE_MAX_WORKERS - Override --max-workers for perspective analysis
#   CLUSTERING_MODEL    - Override clustering keyword model
#   EMBEDDING_MODEL     - Override embedding model
# -----------------------------------------------------------------------------

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"

if [[ $# -gt 1 ]]; then
  echo "Usage: $0 [YYYY-MM-DD]" >&2
  exit 1
fi

RUN_DATE="${1:-$(date +%Y-%m-%d)}"

if ! "$PYTHON_BIN" - "$RUN_DATE" >/dev/null 2>&1 <<'PY'; then
import sys
from datetime import datetime
try:
    datetime.strptime(sys.argv[1], "%Y-%m-%d")
except ValueError:
    sys.exit(1)
PY
  echo "Invalid date format: $RUN_DATE (expected YYYY-MM-DD)" >&2
  exit 1
fi

DATASET_ROOT="$ROOT_DIR/dataset"
DAY_DIR="$DATASET_ROOT/$RUN_DATE"

mkdir -p "$DAY_DIR"

ARXIV_WEB_REL="$RUN_DATE/arxiv_web.json"
ARXIV_WEB_PATH="$DAY_DIR/arxiv_web.json"
AREA_OUTPUT_PATH="$DAY_DIR/arxiv_area_classification.json"
PERSPECTIVE_OUTPUT_PATH="$DAY_DIR/arxiv_research_perspective.json"
CLUSTER_OUTPUT_PATH="$DAY_DIR/arxiv_clustering_results.json"

step() {
  local number="$1"; shift
  local name="$1"; shift
  echo ""
  echo "[$number] $name"
  echo "------------------------------------------------------------------"
}

# 1. Crawl latest arXiv papers
step "1/4" "Crawling arXiv metadata"
WEB_ARGS=(
  --output "$ARXIV_WEB_REL"
)

if [[ -n "${ARXIV_CATEGORIES:-}" ]]; then
  read -r -a _cats <<<"$ARXIV_CATEGORIES"
  WEB_ARGS+=(--categories "${_cats[@]}")
fi

if [[ -n "${WEB_MAX_WORKERS:-}" ]]; then
  WEB_ARGS+=(--max-workers "$WEB_MAX_WORKERS")
fi

if [[ -n "${WEB_DAYS_BACK:-}" ]]; then
  WEB_ARGS+=(--days-back "$WEB_DAYS_BACK")
fi

"$PYTHON_BIN" -B -m arxiv_analyzer.arxiv_web "${WEB_ARGS[@]}"

if [[ ! -s "$ARXIV_WEB_PATH" ]]; then
  echo "Crawler did not produce $ARXIV_WEB_PATH" >&2
  exit 1
fi

# 2. Strategic area classification
step "2/4" "Running area filter classification"
AREA_ARGS=(
  --dataset "$ARXIV_WEB_PATH"
  --output "$AREA_OUTPUT_PATH"
  --model "${AREA_MODEL:-deepseek-reasoner}"
  --temperature "${AREA_TEMPERATURE:-0}"
  --interval "${AREA_REQUEST_INTERVAL:-1.0}"
  --workers "${AREA_WORKERS:-10}"
)

if [[ "${AREA_NO_RESUME:-0}" == "1" || "${AREA_NO_RESUME:-}" == "true" ]]; then
  AREA_ARGS+=(--no-resume)
fi

"$PYTHON_BIN" -B -m arxiv_analyzer.area_filter "${AREA_ARGS[@]}"

if [[ ! -s "$AREA_OUTPUT_PATH" ]]; then
  echo "Area filter did not produce $AREA_OUTPUT_PATH" >&2
  exit 1
fi

# 3. Research perspective analysis
step "3/4" "Generating research perspectives"

"$PYTHON_BIN" -B -m arxiv_analyzer.research_perspective \
  --classification "$AREA_OUTPUT_PATH" \
  --papers "$ARXIV_WEB_PATH" \
  --output "$PERSPECTIVE_OUTPUT_PATH" \
  --workers "${PERSPECTIVE_MAX_WORKERS:-10}" \
  --model "${PERSPECTIVE_MODEL:-deepseek-reasoner}"

if [[ ! -s "$PERSPECTIVE_OUTPUT_PATH" ]]; then
  echo "Perspective analyzer did not produce $PERSPECTIVE_OUTPUT_PATH" >&2
  exit 1
fi

# 4. Clustering
step "4/4" "Clustering papers and extracting keywords"

"$PYTHON_BIN" -B -m arxiv_analyzer.arxiv_clustering \
  --perspective-data "$PERSPECTIVE_OUTPUT_PATH" \
  --paper-metadata "$ARXIV_WEB_PATH" \
  --output "$CLUSTER_OUTPUT_PATH" \
  --clustering-model "${CLUSTERING_MODEL:-deepseek-reasoner}" \
  --embedding-model "${EMBEDDING_MODEL:-text-embedding-ada-002}"

if [[ ! -s "$CLUSTER_OUTPUT_PATH" ]]; then
  echo "Clustering step did not produce $CLUSTER_OUTPUT_PATH" >&2
  exit 1
fi

echo ""
echo "Pipeline completed successfully for $RUN_DATE"
echo "Results stored in: $DAY_DIR"
