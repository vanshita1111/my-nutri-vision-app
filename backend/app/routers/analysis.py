"""
Analysis endpoints: submit a food photo, poll for results, correct items.

Job lifecycle:  queued → processing → complete | failed
Jobs are stored in Redis (TTL 2h) AND persisted to Postgres on completion.
"""

import uuid
import logging
from typing import List
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException

from app.config import settings
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.analysis import AnalysisJobCreate, AnalysisResponse, UserCorrectionRequest, AccuracyRatingRequest
from app.services.s3_service import upload_multiple_images
from app.tasks.pipeline_task import run_analysis_pipeline
from app.core.redis_store import job_create, job_get, job_belongs_to_user
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)
router = APIRouter()

_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/heic", "image/heif"}


@router.post("/analysis", response_model=AnalysisJobCreate, status_code=202)
async def submit_analysis(
    images: List[UploadFile] = File(
        ...,
        description="1–4 JPEG/PNG food photos (max 15 MB each). "
                    "Send multiple for multi-angle / nutrition-label analysis.",
    ),
    current_user: User = Depends(get_current_user),
):
    """
    Upload 1–4 meal photos and start async analysis.
    Multiple photos enable cross-referencing food quantity with nutrition labels.
    Returns a job_id immediately — poll GET /analysis/{job_id} for results.
    """
    if not images:
        raise HTTPException(400, "At least one image is required.")
    if len(images) > 4:
        raise HTTPException(400, "Maximum 4 images per analysis.")

    image_payloads: list[tuple[bytes, str]] = []
    for img in images:
        if img.content_type not in _ALLOWED_CONTENT_TYPES:
            raise HTTPException(400, f"Unsupported format '{img.content_type}'. Use JPEG or PNG.")
        data = await img.read()
        if len(data) > settings.MAX_IMAGE_SIZE_BYTES:
            raise HTTPException(413, f"'{img.filename}' exceeds the 15 MB limit.")
        image_payloads.append((data, img.content_type))

    job_id = str(uuid.uuid4())
    log.info("Analysis submitted job_id=%s user=%s photos=%d", job_id, current_user.id, len(images))

    # Upload all images concurrently
    s3_keys = await upload_multiple_images(image_payloads, job_id)

    # Register job in Redis — abort if unavailable so the task is never orphaned
    if not job_create(job_id, str(current_user.id)):
        raise HTTPException(503, "Job queue temporarily unavailable. Please try again.")

    # Dispatch to Celery worker (list is JSON-serialisable)
    run_analysis_pipeline.delay(job_id, s3_keys, str(current_user.id))

    return AnalysisJobCreate(job_id=job_id)


@router.get("/analysis/{job_id}", response_model=AnalysisResponse)
async def get_analysis_result(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Poll for analysis status.
    Status: queued → processing → complete | failed
    """
    if not job_belongs_to_user(job_id, str(current_user.id)):
        raise HTTPException(404, "Analysis job not found.")

    job = job_get(job_id)
    return AnalysisResponse(
        job_id=job_id,
        status=job["status"],
        result=job.get("result"),
        error=job.get("error"),
        created_at=job.get("created_at"),
        completed_at=job.get("completed_at"),
    )


@router.post("/analysis/{job_id}/correct")
async def correct_food_item(
    job_id: str,
    correction: UserCorrectionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Let users correct a misidentified label or estimated grams.
    Corrections are saved to Postgres and fed back as training signals.
    """
    from app.models.food_item import FoodItem
    from app.models.meal import Meal
    from sqlalchemy import select

    if not job_belongs_to_user(job_id, str(current_user.id)):
        raise HTTPException(404, "Job not found.")

    stmt = (
        select(FoodItem)
        .join(Meal, FoodItem.meal_id == Meal.id)
        .where(FoodItem.id == correction.food_item_id, Meal.user_id == str(current_user.id))
    )
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()

    if item is None:
        raise HTTPException(404, "Food item not found.")

    if not correction.corrected_label and not correction.corrected_grams:
        raise HTTPException(400, "Provide at least one of corrected_label or corrected_grams.")

    if correction.corrected_label:
        item.user_corrected_label = correction.corrected_label
    if correction.corrected_grams:
        item.user_corrected_grams = correction.corrected_grams

    await db.commit()
    log.info(f"Correction saved food_item={item.id} label={correction.corrected_label} grams={correction.corrected_grams}")
    return {"status": "ok", "message": "Correction saved — thank you, this improves the model!"}


@router.post("/analysis/{job_id}/rate", status_code=204)
async def rate_analysis_accuracy(
    job_id: str,
    body: AccuracyRatingRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    1-tap accuracy rating from the user after viewing their analysis result.
    Stored as a training signal against the meal + its photo(s).
    Ratings: accurate | roughly | inaccurate
    """
    from app.models.meal import Meal
    from sqlalchemy import select

    if not job_belongs_to_user(job_id, str(current_user.id)):
        raise HTTPException(404, "Job not found.")

    stmt = select(Meal).where(
        Meal.analysis_job_id == job_id,
        Meal.user_id == str(current_user.id),
    )
    result = await db.execute(stmt)
    meal = result.scalar_one_or_none()

    if meal is None:
        raise HTTPException(404, "Meal not found.")

    meal.accuracy_rating = body.rating
    await db.commit()
    log.info("accuracy_rating saved job=%s meal=%s rating=%s", job_id, meal.id, body.rating)
