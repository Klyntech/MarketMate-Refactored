#!/usr/bin/env bash
# Build custom MATE models from Modelfiles
# Usage: ./build-models.sh [model_name]
# Examples:
#   ./build-models.sh          # Build all models
#   ./build-models.sh nova     # Build only NOVA
#
# Phase 3: 6-layer intelligence stack
#   NOVA   — Fast interpretation layer (public-facing)
#   ATLAS  — Deep market reasoning engine
#   VANTA  — Truth validator + System Builder Agent
#   PRISM  — Data integrity layer (passive, non-agent)
#   VINNI  — Market data intelligence monitor (observation only)
#   OPS    — System operations layer (infrastructure control)
#
# Deprecated (Phase 3):
#   MateMax → replaced by ATLAS
#   MateMini → replaced by NOVA (3b) + VINNI (7b)
#   MateOps → evolved into OPS

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODELS_DIR="${SCRIPT_DIR}/../modelfiles"

# Phase 3: 6-layer intelligence stack
MODELS=("Nova" "Atlas" "Vanta" "Prism" "Vinni" "Ops")
MODEL_NAMES=("mate-nova" "mate-atlas" "mate-vanta" "mate-prism" "mate-vinni" "mate-ops")

# Base models to pull first
BASE_MODELS=("qwen2.5:3b" "qwen2.5:7b")

build_model() {
    local modelfile="$1"
    local name="$2"
    echo "═══════════════════════════════════════"
    echo "Building model: ${name}"
    echo "Modelfile: ${modelfile}"
    echo "═══════════════════════════════════════"
    ollama create "${name}" -f "${modelfile}"
    echo "Model ${name} built successfully"
    echo ""
}

pull_base_models() {
    echo "═══════════════════════════════════════"
    echo "Pulling base models..."
    echo "═══════════════════════════════════════"
    for base in "${BASE_MODELS[@]}"; do
        echo "Pulling ${base}..."
        ollama pull "${base}" || echo "Warning: Failed to pull ${base}, it may already exist"
    done
    echo "Base models ready."
    echo ""
}

if [ $# -eq 0 ]; then
    echo "Building all MATE Phase 3 models..."
    echo ""
    echo "Stack: NOVA → ATLAS → VANTA → PRISM → VINNI → OPS"
    echo "Deprecated: MateMax, MateMini (moved to modelfiles/deprecated/)"
    echo ""

    pull_base_models

    for i in "${!MODELS[@]}"; do
        build_model "${MODELS_DIR}/${MODELS[$i]}" "${MODEL_NAMES[$i]}"
    done

    echo "═══════════════════════════════════════"
    echo "All Phase 3 models built!"
    echo "═══════════════════════════════════════"
    ollama list
else
    TARGET="$1"
    for i in "${!MODELS[@]}"; do
        if [ "${MODEL_NAMES[$i]}" = "${TARGET}" ] || [ "${MODELS[$i]}" = "${TARGET}" ]; then
            build_model "${MODELS_DIR}/${MODELS[$i]}" "${MODEL_NAMES[$i]}"
            exit 0
        fi
    done
    echo "ERROR: Unknown model '${TARGET}'"
    echo "Available: ${MODEL_NAMES[*]}"
    echo "Also try: Nova, Atlas, Vanta, Prism, Vinni, Ops"
    exit 1
fi
