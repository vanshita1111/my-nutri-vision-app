"""
Analysis endpoints: submit a food photo, poll for results, correct items.

Job lifecycle:  queued → processing → complete | failed
Jobs are stored in Redis (TTL 2h) AND persisted to Postgres on completion.
"""

import uuid
import logging
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException

from app.config import settings
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.analysis import AnalysisJobCreate, AnalysisResponse, UserCorrectionRequest
from app.services.s3_service import upload_image_bytes
from app.tasks.pipeline_task import run_analysis_pipeline
from app.core.redis_store import job_create, job_get, job_belongs_to_user
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)
router = APIRouter()


@router.post("/analysis", response_model=AnalysisJobCreate, status_code=202)
async def submit_analysis(
    image: UploadFile = File(..., description="JPEG or PNG food photo (max 15 MB)"),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a meal photo and start async analysis.
    Returns a job_id immediately — poll GET /analysis/{job_id} for results.
    """
    allowed = {"image/jpeg", "image/png", "image/heic", "image/heif"}
    if image.content_type not in allowed:
        raise HTTPException(400, f"Unsupported format '{image.content_type}'. Use JPEG or PNG.")

    image_data = await image.read()
    if len(image_data) > settings.MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(413, "Image exceeds 15 MB limit.")

    job_id = str(uuid.uuid4())
    log.info(f"Analysis submitted job_id={job_id} user={current_user.id}")

    # Upload to S3 / local storage
    s3_key = await upload_image_bytes(image_data, job_id, image.content_type)

    # Register job in Redis — abort if unavailable so the task is never orphaned
    if not job_create(job_id, str(current_user.id)):
        raise HTTPException(503, "Job queue temporarily unavailable. Please try again.")

    # Dispatch to Celery worker
    run_analysis_pipeline.delay(job_id, s3_key, str(current_user.id))

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
