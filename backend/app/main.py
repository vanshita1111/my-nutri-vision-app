"""
FastAPI application entry point.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.config import settings
from app.core.logging import setup_logging
from app.routers import analysis, meals, users, nutrition, coaching

# Initialise structured logging before anything else runs
setup_logging()

import logging
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load ML models on startup, clean up on shutdown."""
    # Lazy import to avoid loading models at import time during tests
    from nutrition_engine.pipeline import NutritionPipeline

    log.info("startup: loading models on device=%s env=%s", settings.DEVICE, settings.APP_ENV)
    app.state.pipeline = NutritionPipeline(device=settings.DEVICE)
    await app.state.pipeline.load_models()
    log.info("startup: models ready")

    yield

    log.info("shutdown: releasing models")
    await app.state.pipeline.cleanup()


app = FastAPI(
    title="Nutrition Vision API",
    description="AI-powered meal analysis: food detection, portion estimation, and nutritional breakdown.",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# ── Middleware ──────────────────────────────────────────────────────────────

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ─────────────────────────────────────────────────────────────────

app.include_router(analysis.router,  prefix="/api/v1", tags=["analysis"])
app.include_router(meals.router,     prefix="/api/v1", tags=["meals"])
app.include_router(users.router,     prefix="/api/v1", tags=["users"])
app.include_router(nutrition.router, prefix="/api/v1", tags=["nutrition"])
app.include_router(coaching.router,  prefix="/api/v1", tags=["coaching"])


# ── Health ───────────────────────────────────────────────────────────────────

@app.get("/health", tags=["system"])
async def health():
    pipeline = getattr(app.state, "pipeline", None)
    return {
        "status": "ok",
        "env": settings.APP_ENV,
        "device": settings.DEVICE,
        "models_loaded": pipeline is not None and pipeline.models_ready,
    }
