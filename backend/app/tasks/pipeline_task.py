"""
Celery task: orchestrates the full analysis pipeline for a submitted image.

Job lifecycle (stored in Redis):
  queued → processing → complete | failed

On completion the result is also persisted to Postgres.
"""

import asyncio
import logging
import os
import tempfile
import uuid

from celery.signals import worker_ready
from app.tasks.celery_app import celery_app
from app.core.redis_store import job_set_processing, job_set_complete, job_set_failed
from app.core.logging import setup_logging

# Workers boot outside the FastAPI lifespan, so we must call setup_logging()
# ourselves so that all log output is structured from the first task.
setup_logging()
log = logging.getLogger(__name__)


@worker_ready.connect
def _pre_warm_pipeline(sender, **kwargs):
    """Load models at worker startup so the first analysis task isn't slow."""
    try:
        _get_pipeline()
        log.info("pipeline pre-warmed on worker startup")
    except Exception as exc:
        log.warning("pipeline pre-warm failed (non-fatal): %s", exc)


# ── Helper: run async code from sync Celery task ──────────────────────────────

def _run(coro):
    """Run a coroutine in a fresh event loop (Celery tasks are synchronous)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Main task ─────────────────────────────────────────────────────────────────

@celery_app.task(bind=True, name="pipeline.run_analysis", max_retries=2)
def run_analysis_pipeline(self, job_id: str, s3_keys: "list[str] | str", user_id: str):
    """
    Main analysis pipeline Celery task.

    Accepts s3_keys as either a list (multi-photo submission) or a single string
    (legacy single-photo format — kept for backward compatibility).

    1. Mark job as processing in Redis
    2. Download all images from S3 to temp files
    3. Load NutritionPipeline models (lazy — cached per worker process)
    4. Run full pipeline (multi-image aware in vision mode)
    5. Persist result to Postgres
    6. Mark job as complete in Redis
    On any exception: mark job as failed and retry up to 2 times.
    """
    # Normalise: legacy single-key string → list
    if isinstance(s3_keys, str):
        s3_keys = [s3_keys]

    log.info(
        "pipeline_task started job_id=%s user_id=%s photos=%d",
        job_id, user_id, len(s3_keys),
    )
    job_set_processing(job_id)

    tmp_paths: list[str] = []
    try:
        from app.services.s3_service import download_image_to_temp

        # Download all images to individual temp files
        for s3_key in s3_keys:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp_path = tmp.name
            _run(download_image_to_temp(s3_key, tmp_path))
            tmp_paths.append(tmp_path)
            log.debug("pipeline_task downloaded job_id=%s key=%s path=%s", job_id, s3_key, tmp_path)

        # Both pipeline + DB persist run in one event loop so asyncpg connections
        # stay bound to the same loop (two separate _run() calls would cause
        # "another operation is in progress" errors on asyncpg).
        pipeline = _get_pipeline()
        result_dict = _run(
            _analyze_and_persist(pipeline, tmp_paths, job_id, user_id, s3_keys)
        )

        if result_dict.get("error") and not result_dict.get("items"):
            log.warning(
                "pipeline returned soft error job_id=%s error=%s",
                job_id, result_dict["error"],
            )
            job_set_failed(job_id, result_dict.get("message", result_dict["error"]))
            return

        job_set_complete(job_id, result_dict)
        log.info(
            "pipeline_task complete job_id=%s items=%d calories=%.0f",
            job_id,
            len(result_dict.get("items", [])),
            result_dict.get("total", {}).get("calories", 0),
        )

    except Exception as exc:
        log.exception("pipeline_task failed job_id=%s error=%s", job_id, exc)
        job_set_failed(job_id, str(exc))
        raise self.retry(exc=exc, countdown=10)

    finally:
        for p in tmp_paths:
            if p and os.path.exists(p):
                os.unlink(p)


# ── Per-process pipeline singleton ───────────────────────────────────────────

_pipeline_instance = None


def _get_pipeline():
    """
    Return a loaded NutritionPipeline, creating and loading it once per
    worker process. Avoids reloading heavy weights on every task.
    """
    global _pipeline_instance
    if _pipeline_instance is None or not _pipeline_instance.models_ready:
        from nutrition_engine.pipeline import NutritionPipeline

        # Read device from env (set in docker-compose / .env)
        device = os.getenv("DEVICE", "cpu")
        log.info("pipeline_task loading models on device=%s (first task in this worker)", device)
        _pipeline_instance = NutritionPipeline(device=device)
        _run(_pipeline_instance.load_models())

    return _pipeline_instance


# ── Combined pipeline + persist (single event loop) ──────────────────────────

async def _analyze_and_persist(
    pipeline, tmp_paths: "list[str]", job_id: str, user_id: str, s3_keys: "list[str]"
) -> dict:
    """Run the full pipeline then persist to DB — all in one event loop so
    asyncpg connections stay bound to the correct loop throughout."""
    result_dict = await pipeline.analyze(tmp_paths)

    # Calculate blood sugar impact whenever we have real food items
    if result_dict.get("items") and not result_dict.get("error"):
        try:
            from nutrition_engine.blood_sugar_estimator import estimate_blood_sugar_impact
            result_dict["blood_sugar_impact"] = estimate_blood_sugar_impact(
                result_dict["items"], result_dict["total"]
            )
        except Exception as bs_exc:
            log.warning("blood_sugar_estimator failed (non-fatal): %s", bs_exc)

    if not (result_dict.get("error") and not result_dict.get("items")):
        await _persist_result(job_id, user_id, s3_keys, result_dict)
    return result_dict


# ── DB persistence ────────────────────────────────────────────────────────────

async def _persist_result(job_id: str, user_id: str, s3_keys: "list[str]", result: dict):
    """Save analysis result to PostgreSQL (meal + food_items rows).

    Creates a fresh engine with NullPool on every call so that asyncpg
    connections are never reused across event loops (each Celery task spins
    up its own event loop via _run(), and pooled connections from a prior
    closed loop raise 'Future attached to a different loop').
    """
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy import pool as sa_pool
    from app.config import settings
    from app.models.meal import Meal
    from app.models.food_item import FoodItem

    engine = create_async_engine(settings.DATABASE_URL, poolclass=sa_pool.NullPool)
    _Session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )

    try:
        async with _Session() as db:
            total = result.get("total", {})
            bs = result.get("blood_sugar_impact") or {}
            meal = Meal(
                id=str(uuid.uuid4()),
                user_id=user_id,
                analysis_job_id=job_id,
                image_s3_key=s3_keys[0],        # primary (backwards compat)
                all_image_s3_keys=s3_keys,       # all photos — training data asset
                total_calories=total.get("calories", 0),
                total_protein_g=total.get("protein_g", 0),
                total_fat_g=total.get("fat_g", 0),
                total_carbs_g=total.get("carbs_g", 0),
                total_fiber_g=total.get("fiber_g", 0),
                llm_notes=result.get("llm_notes", ""),
                analysis_version=result.get("analysis_version", "2.0"),
                blood_sugar_score=bs.get("score"),
                blood_sugar_level=bs.get("level"),
                blood_sugar_data=bs if bs else None,
            )
            db.add(meal)

            for item_data in result.get("items", []):
                n = item_data.get("nutrition", {})
                fi = FoodItem(
                    id=str(uuid.uuid4()),
                    meal_id=meal.id,
                    label=item_data.get("label", "unknown"),
                    estimated_grams=item_data.get("grams", 0),
                    gram_confidence=item_data.get("gram_confidence", "low"),
                    is_hidden_ingredient=item_data.get("is_hidden_ingredient", False),
                    calories=n.get("calories", 0),
                    protein_g=n.get("protein_g", 0),
                    fat_g=n.get("fat_g", 0),
                    carbs_g=n.get("carbs_g", 0),
                    fiber_g=n.get("fiber_g", 0),
                    nutrition_source=item_data.get("nutrition_source", "fallback"),
                )
                db.add(fi)

            await db.commit()
            log.debug("pipeline_task persisted to DB meal_id=%s", meal.id)
    finally:
        await engine.dispose()
