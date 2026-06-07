#!/usr/bin/env bash
# =============================================================================
# MarketMate — Cloudflare Tunnel Helper
# =============================================================================
# Starts a Cloudflare quick tunnel that exposes the local Ollama instance
# to the internet via a randomly-generated URL. Useful for:
#   - Remote testing of the Ollama API
#   - Connecting cloud-hosted MarketMate to a local Ollama instance
#   - Development & debugging without port-forwarding
#
# Prerequisites:
#   - cloudflared installed (https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)
#   - Ollama running locally on port 11434
#
# Usage:
#   ./scripts/tunnel.sh
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
LOCAL_PORT="${OLLAMA_PORT:-11434}"
LOCAL_URL="http://localhost:${LOCAL_PORT}"
TUNNEL_CMD="cloudflared tunnel --url ${LOCAL_URL}"

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------
log()  { echo "[tunnel] $(date '+%Y-%m-%d %H:%M:%S') — $*"; }
warn() { echo "[tunnel] WARNING: $*" >&2; }
die()  { echo "[tunnel] FATAL: $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
log "Checking for cloudflared..."
if ! command -v cloudflared &> /dev/null; then
    die "cloudflared is not installed. See: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
fi

log "Checking if Ollama is running on ${LOCAL_URL}..."
if ! curl -sf "${LOCAL_URL}/api/tags" > /dev/null 2>&1; then
    warn "Ollama does not appear to be running on ${LOCAL_URL}."
    warn "Start it first with: ollama serve"
    read -rp "Continue anyway? [y/N] " confirm
    [[ "${confirm,,}" != "y" ]] && die "Aborted."
fi

# ---------------------------------------------------------------------------
# Start the tunnel and capture the generated URL
# ---------------------------------------------------------------------------
log "Starting Cloudflare quick tunnel -> ${LOCAL_URL}..."
log "─────────────────────────────────────────────────────────────────────"

# cloudflared prints the tunnel URL to stderr. We capture it.
TUNNEL_URL=""
TEMP_LOG=$(mktemp)

# Start cloudflared in background, capturing output
$TUNNEL_CMD 2>&1 | tee "$TEMP_LOG" &
TUNNEL_PID=$!

# Wait for the URL to appear in the output (cloudflared prints it once ready)
log "Waiting for tunnel URL..."
for i in $(seq 1 30); do
    TUNNEL_URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$TEMP_LOG" | head -1 || true)
    if [ -n "$TUNNEL_URL" ]; then
        break
    fi
    sleep 2
done

# ---------------------------------------------------------------------------
# Print instructions
# ---------------------------------------------------------------------------
echo ""
log "═══════════════════════════════════════════════════════════════════════"
log "  Cloudflare Tunnel is ACTIVE"
log "═══════════════════════════════════════════════════════════════════════"
echo ""
if [ -n "$TUNNEL_URL" ]; then
    log "  Tunnel URL:  ${TUNNEL_URL}"
    echo ""
    log "  Set this in your .env or environment:"
    log "    OLLAMA_BASE_URL=${TUNNEL_URL}/v1"
    echo ""
    log "  Example curl test:"
    log "    curl ${TUNNEL_URL}/api/tags"
else
    warn "  Could not auto-detect the tunnel URL."
    warn "  Check the cloudflared output above for the generated URL."
    warn "  It will look like: https://<random>.trycloudflare.com"
fi
echo ""
log "  Press Ctrl+C to stop the tunnel."
log "═══════════════════════════════════════════════════════════════════════"

# ---------------------------------------------------------------------------
# Keep script alive — wait for cloudflared
# ---------------------------------------------------------------------------
cleanup() {
    log "Shutting down tunnel (PID ${TUNNEL_PID})..."
    kill $TUNNEL_PID 2>/dev/null || true
    rm -f "$TEMP_LOG"
    log "Tunnel stopped."
}
trap cleanup EXIT INT TERM

wait $TUNNEL_PID
