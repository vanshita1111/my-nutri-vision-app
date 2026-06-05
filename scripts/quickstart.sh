#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# Nutrition Vision — Quickstart
#
# Runs the complete backend stack (API + worker + Redis + Postgres) locally
# using Docker Compose.  No GPU, no model weights required to start.
#
# Usage:
#   bash scripts/quickstart.sh          # first-time setup + start
#   bash scripts/quickstart.sh --reset  # nuke volumes and start fresh
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail
cd "$(dirname "$0")/.."

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[setup]${NC} $*"; }
warn()  { echo -e "${YELLOW}[warn] ${NC} $*"; }
error() { echo -e "${RED}[error]${NC} $*" >&2; }

# ── Prereq checks ─────────────────────────────────────────────────────────────

command -v docker >/dev/null 2>&1 || { error "Docker not found. Install from https://docs.docker.com/get-docker/"; exit 1; }
docker compose version >/dev/null 2>&1 || { error "Docker Compose V2 not found. Update Docker Desktop to 4.x+."; exit 1; }

# ── Reset flag ────────────────────────────────────────────────────────────────

if [[ "${1:-}" == "--reset" ]]; then
  warn "Resetting — stopping containers and removing volumes..."
  docker compose down -v --remove-orphans 2>/dev/null || true
fi

# ── .env setup ────────────────────────────────────────────────────────────────

if [[ ! -f .env ]]; then
  info "Creating .env from .env.example..."
  cp .env.example .env

  # Generate a random JWT secret
  JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null \
    || openssl rand -hex 32 2>/dev/null \
    || echo "change-me-$(date +%s)")
  sed -i.bak "s/SECRET_KEY=.*/SECRET_KEY=${JWT_SECRET}/" .env && rm -f .env.bak

  warn "A default .env file was created."
  warn "Add your ANTHROPIC_API_KEY to .env for AI-powered coaching and LLM validation."
  warn "Add your USDA_API_KEY for broader food database coverage (optional)."
  echo
fi

# ── Build images ──────────────────────────────────────────────────────────────

info "Building Docker images (this may take a few minutes on first run)..."
docker compose build

# ── Start services ────────────────────────────────────────────────────────────

info "Starting services: postgres, redis, api, worker, flower..."
docker compose up -d postgres redis

info "Waiting for Postgres to be ready..."
for i in $(seq 1 30); do
  if docker compose exec -T postgres pg_isready -U nutrition -d nutrition_vision >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

info "Running database migrations..."
docker compose run --rm api alembic upgrade head

info "Starting API and Celery worker..."
docker compose up -d api worker flower

# ── Health check ──────────────────────────────────────────────────────────────

info "Waiting for API to be healthy..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo
echo -e "${GREEN}══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Nutrition Vision is running!${NC}"
echo -e "${GREEN}══════════════════════════════════════════════════${NC}"
echo
echo "  API:              http://localhost:8000"
echo "  Interactive docs: http://localhost:8000/docs"
echo "  Celery dashboard: http://localhost:5555"
echo
echo "  Health check:"
curl -s http://localhost:8000/health | python3 -m json.tool 2>/dev/null || echo "  (run manually: curl http://localhost:8000/health)"
echo
echo "  To start the mobile app:"
echo "    cd frontend && npm install && npx expo start"
echo
echo "  To view logs:"
echo "    docker compose logs -f api"
echo "    docker compose logs -f worker"
echo
echo "  To stop everything:"
echo "    docker compose down"
echo
