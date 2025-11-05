#!/bin/bash

# Research Paper Clustering Pipeline
# This script runs the complete clustering analysis on research papers

set -euo pipefail
export PATH=$PATH:$(pwd)
PYTHON_BIN="${PYTHON_BIN:-python}"

RUN_DATE="${RUN_DATE:-$(date +%Y-%m-%d)}"
DATASET_DIR="dataset/$RUN_DATE"
PERSPECTIVE_PATH="${PERSPECTIVE_PATH:-"$DATASET_DIR/arxiv_research_perspective.json"}"
METADATA_PATH="${METADATA_PATH:-"$DATASET_DIR/arxiv_web.json"}"
OUTPUT_PATH="${OUTPUT_PATH:-"$DATASET_DIR/arxiv_clustering_results.json"}"

echo "Starting Research Paper Clustering Pipeline for $RUN_DATE..."

# Check if required files exist
if [ ! -f "$PERSPECTIVE_PATH" ]; then
    echo "Error: $PERSPECTIVE_PATH not found"
    echo "Please run the research perspective analysis first"
    exit 1
fi

if [ ! -f "$METADATA_PATH" ]; then
    echo "Error: $METADATA_PATH not found"
    echo "Please run the arXiv web crawler first"
    exit 1
fi

echo "✓ Found required data files"

# Run the clustering pipeline
echo "Running clustering analysis..."
exec "$PYTHON_BIN" -B -m arxiv_analyzer.arxiv_clustering \
    --perspective-data "$PERSPECTIVE_PATH" \
    --paper-metadata "$METADATA_PATH" \
    --output "$OUTPUT_PATH" \
    --clustering-model "${CLUSTERING_MODEL:-deepseek-reasoner}" \
    --embedding-model "${EMBEDDING_MODEL:-text-embedding-ada-002}"
