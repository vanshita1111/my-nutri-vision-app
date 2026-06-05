"""
Pytest configuration and shared fixtures for the backend test suite.

asyncio_mode = auto is set in pytest.ini, so:
  - All async fixtures/tests run automatically under asyncio
  - No need for @pytest.mark.asyncio or @pytest_asyncio.fixture decorators
  - No manual event_loop fixture required
"""

import os
import sys
import pytest
from pathlib import Path

# Add backend root and project root to sys.path so `app` and `nutrition_engine` resolve
sys.path.insert(0, str(Path(__file__).parent.parent))        # backend/
sys.path.insert(0, str(Path(__file__).parent.parent.parent)) # project root

# Minimal test environment — no real DB / GPU / API keys needed.
# Set these BEFORE importing any app modules so pydantic-settings picks them up.
os.environ.setdefault("DATABASE_URL",      "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY",        "test-secret-key-for-pytest-use-only!!")
os.environ.setdefault("DEVICE",            "cpu")
os.environ.setdefault("YOLO_MODEL_PATH",   "models/weights/food_detector_v1.onnx")
os.environ.setdefault("SAM2_MODEL_PATH",   "models/weights/sam2_hiera_large.pt")
os.environ.setdefault("ANTHROPIC_API_KEY", "")   # LLM disabled in tests
os.environ.setdefault("USDA_API_KEY",      "")   # USDA disabled in tests
os.environ.setdefault("APP_ENV",           "development")
os.environ.setdefault("MIN_BLUR_SCORE",    "20")  # Relax blur check for synthetic test images


# ── Test database ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
async def db_engine():
    """
    In-memory SQLite engine shared across the whole test session.

    Uses StaticPool so every connection (including the ones opened by the
    app's dependency-overridden get_db) sees the same in-memory database.
    Tables are created once here and persist for the entire session.
    """
    from sqlalchemy.pool import StaticPool
    from sqlalchemy.ext.asyncio import create_async_engine
    from app.database import Base
    from app.models import user, meal, food_item  # noqa: F401 — registers models

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    """Fresh async DB session per test; rolls back after each test."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    factory = async_sessionmaker(db_engine, expire_on_commit=False, autoflush=False)
    async with factory() as session:
        yield session
        await session.rollback()


# ── HTTP test client ───────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
async def client(db_engine):
    """
    Async HTTP client wired to the FastAPI ASGI app.

    Overrides the get_db dependency so every route uses the same in-memory
    SQLite engine (db_engine) where tables have already been created.
    ASGITransport does not trigger the app lifespan, so model loading is
    skipped — routes that need the pipeline will return 503, which is fine
    for these integration tests.
    """
    from httpx import AsyncClient, ASGITransport
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from app.main import app
    from app.dependencies import get_db

    factory = async_sessionmaker(db_engine, expire_on_commit=False, autoflush=False)

    async def _override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Test image ─────────────────────────────────────────────────────────────────

@pytest.fixture
def test_image_path(tmp_path) -> str:
    """
    Synthetic 640×640 BGR image with a white circle on a dark background.
    The high grayscale contrast (40 vs 255) ensures a sharp Laplacian edge
    so the blur check passes at MIN_BLUR_SCORE=20.
    """
    import cv2
    import numpy as np
    img = np.full((640, 640, 3), 40, dtype=np.uint8)          # dark grey
    cv2.circle(img, (320, 320), 150, (255, 255, 255), -1)      # white circle
    path = str(tmp_path / "test_meal.jpg")
    cv2.imwrite(path, img)
    return path


# ── Auth helpers ──────────────────────────────────────────────────────────────

@pytest.fixture
async def auth_headers(client) -> dict:
    """Register a test user and return Bearer token headers."""
    resp = await client.post("/api/v1/auth/register", json={
        "email":     "test@nutrivision.io",
        "password":  "testpassword123",
        "full_name": "Test User",
    })
    if resp.status_code not in (200, 201):
        # User already exists from a previous test — log in instead
        resp = await client.post("/api/v1/auth/login", json={
            "email":    "test@nutrivision.io",
            "password": "testpassword123",
        })
    token = resp.json().get("access_token", "")
    return {"Authorization": f"Bearer {token}"}
