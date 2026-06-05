"""
Redis-backed job store for analysis pipeline jobs.
Replaces the in-memory dict so jobs survive worker restarts
and work correctly across multiple API processes.

Job TTL: 2 hours (jobs are ephemeral — results are also persisted to Postgres)
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional
import redis

from app.config import settings

log = logging.getLogger(__name__)

# Synchronous Redis client (used in Celery tasks and FastAPI sync paths)
_redis_client: Optional[redis.Redis] = None

JOB_TTL_SECONDS = 7200  # 2 hours
KEY_PREFIX = "nv:job:"


def _get_client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def _key(job_id: str) -> str:
    return f"{KEY_PREFIX}{job_id}"


# ── Write ─────────────────────────────────────────────────────────────────────

def job_create(job_id: str, user_id: str) -> bool:
    """Store the job in Redis. Returns False if Redis is unavailable."""
    data = {
        "job_id":     job_id,
        "user_id":    user_id,
        "status":     "queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        _get_client().setex(_key(job_id), JOB_TTL_SECONDS, json.dumps(data))
        return True
    except redis.RedisError as exc:
        log.warning("Redis unavailable — job_create failed for %s: %s", job_id, exc)
        return False


def job_set_processing(job_id: str) -> None:
    _job_update(job_id, {"status": "processing"})


def job_set_complete(job_id: str, result: dict) -> None:
    _job_update(job_id, {
        "status":       "complete",
        "result":       result,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    })


def job_set_failed(job_id: str, error: str) -> None:
    _job_update(job_id, {
        "status":       "failed",
        "error":        error,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    })


def _job_update(job_id: str, updates: dict) -> None:
    try:
        r = _get_client()
        key = _key(job_id)
        raw = r.get(key)
        if raw:
            data = json.loads(raw)
            data.update(updates)
            ttl = r.ttl(key)
            r.setex(key, max(ttl, 60), json.dumps(data))
    except redis.RedisError as exc:
        log.warning("Redis unavailable — _job_update skipped for %s: %s", job_id, exc)


# ── Read ──────────────────────────────────────────────────────────────────────

def job_get(job_id: str) -> Optional[dict]:
    try:
        raw = _get_client().get(_key(job_id))
        return json.loads(raw) if raw else None
    except redis.RedisError as exc:
        log.warning("Redis unavailable — job_get returning None for %s: %s", job_id, exc)
        return None


def job_belongs_to_user(job_id: str, user_id: str) -> bool:
    job = job_get(job_id)
    return job is not None and job.get("user_id") == user_id
