#!/usr/bin/env bash
# =============================================================================
# MarketMate — Ollama Startup Script
# =============================================================================
# This script:
#   1. Starts Ollama in the background
#   2. Waits for the API to become healthy
#   3. Pulls the configured model (if not already present)
#   4. Runs a warm-up inference to load the model into memory
#   5. Keeps the foreground process alive
#
# Environment variables:
#   OLLAMA_MODEL  — model tag to pull & load (default: qwen2.5:7b)
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MODEL="${OLLAMA_MODEL:-qwen2.5:7b}"
OLLAMA_URL="http://localhost:11434"
MAX_WAIT_SECONDS=120
POLL_INTERVAL=2

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------
log()  { echo "[ollama-startup] $(date '+%Y-%m-%d %H:%M:%S') — $*"; }
warn() { echo "[ollama-startup] WARNING: $*" >&2; }
die()  { echo "[ollama-startup] FATAL: $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Step 1: Start Ollama server in the background
# ---------------------------------------------------------------------------
log "Starting Ollama server in background..."
ollama serve &
OLLAMA_PID=$!
log "Ollama PID: ${OLLAMA_PID}"

# ---------------------------------------------------------------------------
# Step 2: Wait for Ollama to become ready
# ---------------------------------------------------------------------------
log "Waiting for Ollama API at ${OLLAMA_URL}/api/tags (max ${MAX_WAIT_SECONDS}s)..."
elapsed=0
while [ $elapsed -lt $MAX_WAIT_SECONDS ]; do
    if curl -sf "${OLLAMA_URL}/api/tags" > /dev/null 2>&1; then
        log "Ollama API is ready."
        break
    fi
    sleep $POLL_INTERVAL
    elapsed=$((elapsed + POLL_INTERVAL))
done

if [ $elapsed -ge $MAX_WAIT_SECONDS ]; then
    die "Ollama did not become ready within ${MAX_WAIT_SECONDS}s"
fi

# ---------------------------------------------------------------------------
# Step 3: Pull the model (idempotent — skips if already present)
# ---------------------------------------------------------------------------
log "Pulling model: ${MODEL}..."
if ollama pull "$MODEL"; then
    log "Model '${MODEL}' is available."
else
    warn "Failed to pull model '${MODEL}'. It may already be present from the build stage."
fi

# ---------------------------------------------------------------------------
# Step 4: Warm-up inference — pre-load the model into memory
# ---------------------------------------------------------------------------
log "Running warm-up inference to pre-load '${MODEL}' into memory..."
WARMUP_RESPONSE=$(curl -sf "${OLLAMA_URL}/api/generate" \
    -d "{\"model\": \"${MODEL}\", \"prompt\": \"Hello, MATE is online.\", \"stream\": false}" \
    2>&1 || true)

if echo "$WARMUP_RESPONSE" | grep -q "response"; then
    log "Warm-up inference completed successfully."
else
    warn "Warm-up inference may have failed. Response: ${WARMUP_RESPONSE}"
fi

# ---------------------------------------------------------------------------
# Step 5: Keep foreground alive — wait on the Ollama process
# ---------------------------------------------------------------------------
log "Ollama startup complete. Model '${MODEL}' is loaded and ready."
log "Keeping foreground alive (waiting on Ollama PID ${OLLAMA_PID})..."

wait $OLLAMA_PID
