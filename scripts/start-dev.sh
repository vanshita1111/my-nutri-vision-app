#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# start-dev.sh — one command to start the full NutriVision dev stack:
#   1. Docker backend (API + Celery + Postgres + Redis)
#   2. ngrok tunnel → auto-patches frontend/.env with the live URL
#   3. Expo Metro bundler (frontend)
#
# Usage:
#   ./scripts/start-dev.sh           # start everything
#   ./scripts/start-dev.sh --no-expo # backend + tunnel only (start expo manually)
# ──────────────────────────────────────────────────────────────────────────────

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$SCRIPT_DIR/.."
FRONTEND="$ROOT/frontend"
ENV_FILE="$FRONTEND/.env"
NGROK_LOG="/tmp/nutrivision-ngrok.log"
EXPO_LOG="/tmp/nutrivision-expo.log"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[dev]${NC} $*"; }
warn() { echo -e "${YELLOW}[dev]${NC} $*"; }
err()  { echo -e "${RED}[dev]${NC} $*"; }

# ── 1. Docker backend ─────────────────────────────────────────────────────────
log "Starting Docker services..."
cd "$ROOT"
docker compose up -d --build 2>&1 | tail -6

# Wait for API to be healthy
log "Waiting for API to be ready..."
for i in $(seq 1 20); do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        log "API is healthy"
        break
    fi
    sleep 2
    if [ $i -eq 20 ]; then
        err "API did not start in time. Check: docker compose logs api"
        exit 1
    fi
done

# ── 2. ngrok tunnel ───────────────────────────────────────────────────────────
log "Starting ngrok tunnel on port 8000..."

# Kill any existing ngrok on this port
pkill -f "ngrok http 8000" 2>/dev/null || true
sleep 1

# Start ngrok
ngrok http 8000 --log=stdout > "$NGROK_LOG" 2>&1 &
NGROK_PID=$!

# Wait for the URL to appear
API_URL=""
for i in $(seq 1 15); do
    API_URL=$(grep -oE "https://[a-zA-Z0-9_-]+\.ngrok[a-zA-Z0-9._-]+" "$NGROK_LOG" 2>/dev/null | head -1)
    [ -n "$API_URL" ] && break
    sleep 1
done

if [ -z "$API_URL" ]; then
    # ngrok not authenticated or quota hit — fall back to local IP
    warn "ngrok tunnel failed. Falling back to local IP..."
    LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)
    if [ -n "$LOCAL_IP" ]; then
        API_URL="http://$LOCAL_IP:8000"
        warn "Using local IP: $API_URL"
        warn "If the phone can't connect, your router has AP isolation."
        warn "Fix: router admin > Wireless > disable 'Client Isolation'"
    else
        err "Could not determine local IP. Start Expo manually and set EXPO_PUBLIC_API_URL."
        exit 1
    fi
else
    log "ngrok tunnel active: $API_URL"
fi

# ── 3. Patch frontend/.env ────────────────────────────────────────────────────
FULL_URL="${API_URL}/api/v1"
log "Patching $ENV_FILE  →  $FULL_URL"

if grep -q "EXPO_PUBLIC_API_URL" "$ENV_FILE" 2>/dev/null; then
    # Update existing line (macOS-compatible sed)
    sed -i '' "s|EXPO_PUBLIC_API_URL=.*|EXPO_PUBLIC_API_URL=${FULL_URL}|" "$ENV_FILE"
else
    echo "EXPO_PUBLIC_API_URL=${FULL_URL}" >> "$ENV_FILE"
fi

echo ""
log "──────────────────────────────────────────"
log " Backend  : http://localhost:8000"
log " API docs : http://localhost:8000/docs"
log " Flower   : http://localhost:5555"
log " Phone URL: $FULL_URL"
log "──────────────────────────────────────────"
echo ""

# ── 4. Expo ───────────────────────────────────────────────────────────────────
if [[ "$*" == *"--no-expo"* ]]; then
    log "Skipping Expo (--no-expo flag). Start it with: make frontend-clear"
    exit 0
fi

log "Starting Expo (Metro bundler)..."
cd "$FRONTEND"

# Trap Ctrl+C to shut down ngrok cleanly
cleanup() {
    echo ""
    log "Shutting down..."
    kill $NGROK_PID 2>/dev/null || true
    pkill -f "expo start" 2>/dev/null || true
}
trap cleanup INT TERM

npx expo start --tunnel --clear
