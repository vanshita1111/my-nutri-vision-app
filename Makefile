# ── NutriVision — Makefile ─────────────────────────────────────────────────────
# Usage: make <target>
#
.PHONY: help \
        mobile \
        dev stop clean logs shell-api shell-db \
        prod prod-stop prod-logs prod-build \
        test test-pipeline lint \
        migrate migrate-create migrate-docker \
        seed-db backup-db \
        download-models train-detector train-classifier evaluate \
        frontend-install frontend-start frontend-ios frontend-android frontend-clear \
        check-env venv run-local run-worker

# ── Help ──────────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "  ── Development ─────────────────────────────────────────────────"
	@echo "  make mobile            START HERE — backend + ngrok tunnel + Expo (one command)"
	@echo "  make mobile-backend    Backend + tunnel only (start Expo separately)"
	@echo "  make dev               Docker backend only (no tunnel, no Expo)"
	@echo "  make stop              Stop all dev services"
	@echo "  make clean             Stop + remove volumes (⚠ deletes all data)"
	@echo "  make logs              Tail api + worker logs"
	@echo "  make shell-api         Bash shell inside the api container"
	@echo "  make shell-db          psql shell inside postgres container"
	@echo ""
	@echo "  ── Production ──────────────────────────────────────────────────"
	@echo "  make prod              Deploy production stack"
	@echo "  make prod-build        Rebuild production images without starting"
	@echo "  make prod-stop         Stop production stack"
	@echo "  make prod-logs         Tail production logs"
	@echo ""
	@echo "  ── Database ────────────────────────────────────────────────────"
	@echo "  make migrate           Run Alembic migrations (local venv)"
	@echo "  make migrate-docker    Run Alembic migrations inside Docker"
	@echo "  make migrate-create name=<desc>  Create new migration"
	@echo "  make seed-db           Load IFCT/USDA nutrition data"
	@echo "  make backup-db         Dump database to backups/"
	@echo ""
	@echo "  ── Testing & Linting ───────────────────────────────────────────"
	@echo "  make test              Run all backend tests"
	@echo "  make test-pipeline     Run pipeline tests with verbose output"
	@echo "  make lint              Lint + auto-fix with ruff"
	@echo ""
	@echo "  ── ML Models ───────────────────────────────────────────────────"
	@echo "  make download-models   Download pretrained YOLOv8 weights"
	@echo "  make train-detector    Fine-tune YOLOv8 on food dataset"
	@echo "  make train-classifier  Train EfficientNet-B3 secondary classifier"
	@echo "  make evaluate          Evaluate both models on validation set"
	@echo ""
	@echo "  ── Frontend ────────────────────────────────────────────────────"
	@echo "  make frontend-install  npm install"
	@echo "  make frontend-start    npx expo start"
	@echo "  make frontend-clear    npx expo start --clear (wipes Metro cache)"
	@echo "  make frontend-ios      Run on iOS simulator"
	@echo "  make frontend-android  Run on Android emulator"
	@echo ""

# ── Development ───────────────────────────────────────────────────────────────

## One-command dev startup — backend + ngrok tunnel + Expo
## Run this every time you want to develop. Zero manual config needed.
mobile:
	@bash scripts/start-dev.sh

## Backend only (no Expo)
mobile-backend:
	@bash scripts/start-dev.sh --no-expo

dev: check-env
	docker compose up --build -d
	@echo ""
	@echo "  ✓ NutriVision is running"
	@echo "  API docs: http://localhost:8000/docs"
	@echo "  Flower:   http://localhost:5555"
	@echo ""

stop:
	docker compose down

clean:
	@echo "WARNING: This removes all volumes (database, redis, images)."
	@read -p "Are you sure? [y/N] " yn; \
	if [ "$$yn" = "y" ]; then \
	  docker compose down -v --remove-orphans; \
	  echo "Done."; \
	else \
	  echo "Cancelled."; \
	fi

logs:
	docker compose logs -f api worker

shell-api:
	docker compose exec api bash

shell-db:
	docker compose exec postgres psql -U $${POSTGRES_USER:-nutrition} -d nutrition_vision

# ── Production ────────────────────────────────────────────────────────────────

prod: check-env
	docker compose -f docker-compose.prod.yml up -d
	@echo ""
	@echo "  ✓ Production stack started"
	@echo "  Check health: curl https://api.nutrivision.app/health"
	@echo ""

prod-build:
	docker compose -f docker-compose.prod.yml build --no-cache

prod-stop:
	docker compose -f docker-compose.prod.yml down

prod-logs:
	docker compose -f docker-compose.prod.yml logs -f api worker

# ── Local development (without Docker) ───────────────────────────────────────

venv:
	python3 -m venv venv
	./venv/bin/pip install --upgrade pip
	./venv/bin/pip install -r backend/requirements.txt
	@echo "Activate with: source venv/bin/activate"

run-local:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-worker:
	cd backend && celery -A app.tasks.celery_app worker --loglevel=info --concurrency=1

# ── Database ──────────────────────────────────────────────────────────────────

migrate:
	cd backend && alembic upgrade head

# Run migrations inside the running Docker api container (prod-safe)
migrate-docker:
	docker compose exec api alembic upgrade head

migrate-create:
	@test -n "$(name)" || (echo "Usage: make migrate-create name=<description>" && exit 1)
	cd backend && alembic revision --autogenerate -m "$(name)"

seed-db:
	cd datasets && python build_ifct_db.py
	@echo "IFCT nutrition data loaded."

backup-db:
	@mkdir -p backups
	@TIMESTAMP=$$(date +%Y%m%d_%H%M%S); \
	docker compose exec -T postgres pg_dump \
	  -U $${POSTGRES_USER:-nutrition} nutrition_vision \
	  | gzip > backups/nutrition_vision_$$TIMESTAMP.sql.gz; \
	echo "Backup saved: backups/nutrition_vision_$$TIMESTAMP.sql.gz"

# ── Testing & Linting ─────────────────────────────────────────────────────────

test:
	cd backend && python -m pytest tests/ -v --tb=short

test-pipeline:
	cd backend && python -m pytest tests/test_pipeline.py -v -s

lint:
	cd backend && ruff check . --fix
	cd backend && ruff format .

# ── ML Models ─────────────────────────────────────────────────────────────────

download-models:
	mkdir -p models/weights
	@echo "Downloading YOLOv8m pretrained weights (COCO)..."
	python3 -c "from ultralytics import YOLO; YOLO('yolov8m.pt')"
	@echo ""
	@echo "  ✓ YOLOv8m downloaded to ~/.config/Ultralytics/"
	@echo "  Depth Anything v2 downloads automatically on first inference."
	@echo "  Run: make train-detector   to fine-tune on food data."
	@echo ""

train-detector:
	cd training && python scripts/train_detector.py

train-classifier:
	cd training && python scripts/train_classifier.py

evaluate:
	cd training && python scripts/evaluate_models.py

# ── Frontend ──────────────────────────────────────────────────────────────────

frontend-install:
	cd frontend && npm install --legacy-peer-deps

frontend-start:
	cd frontend && npx expo start

frontend-clear:
	cd frontend && npx expo start --clear

frontend-ios:
	cd frontend && npx expo run:ios

frontend-android:
	cd frontend && npx expo run:android

# ── Utilities ─────────────────────────────────────────────────────────────────

check-env:
	@test -f .env || (echo "ERROR: .env not found. Run: cp .env.example .env" && exit 1)
	@grep -q "ANTHROPIC_API_KEY=sk-ant" .env || \
	  echo "WARNING: ANTHROPIC_API_KEY not set in .env — coaching features won't work"
