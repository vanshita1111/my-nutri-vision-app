"""
API endpoint tests — auth, analysis, meals, nutrition.
Uses the in-memory SQLite DB and async HTTP client from conftest.py.
"""

import pytest


# ── Auth ─────────────────────────────────────────────────────────────────────

async def test_register_creates_user(client):
    resp = await client.post("/api/v1/auth/register", json={
        "email":     "newuser@test.io",
        "password":  "password123",
        "full_name": "New User",
    })
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


async def test_login_with_valid_credentials(client):
    # Register first
    await client.post("/api/v1/auth/register", json={
        "email": "logintest@test.io", "password": "pass1234"
    })
    # Then login
    resp = await client.post("/api/v1/auth/login", json={
        "email": "logintest@test.io", "password": "pass1234"
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_login_wrong_password(client):
    await client.post("/api/v1/auth/register", json={
        "email": "badlogin@test.io", "password": "correct_password"
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": "badlogin@test.io", "password": "wrong_password"
    })
    assert resp.status_code == 401


async def test_get_profile_requires_auth(client):
    resp = await client.get("/api/v1/me")
    assert resp.status_code in (401, 403)  # HTTPBearer varies by FastAPI version


async def test_get_profile_authenticated(client, auth_headers):
    resp = await client.get("/api/v1/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "email" in data
    assert "is_premium" in data


# ── Analysis ──────────────────────────────────────────────────────────────────

async def test_submit_analysis_requires_auth(client, test_image_path):
    with open(test_image_path, "rb") as f:
        resp = await client.post("/api/v1/analysis", files={"image": ("meal.jpg", f, "image/jpeg")})
    assert resp.status_code in (401, 403)  # HTTPBearer varies by FastAPI version


async def test_submit_analysis_invalid_format(client, auth_headers):
    resp = await client.post(
        "/api/v1/analysis",
        headers=auth_headers,
        files={"image": ("file.txt", b"not an image", "text/plain")},
    )
    assert resp.status_code == 400


async def test_get_nonexistent_job(client, auth_headers):
    resp = await client.get("/api/v1/analysis/nonexistent-job-id", headers=auth_headers)
    assert resp.status_code == 404


# ── Meals ─────────────────────────────────────────────────────────────────────

async def test_list_meals_empty(client, auth_headers):
    resp = await client.get("/api/v1/meals", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_daily_nutrition_empty(client, auth_headers):
    resp = await client.get("/api/v1/nutrition/daily?days=7", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ── Nutrition ─────────────────────────────────────────────────────────────────

async def test_food_search(client, auth_headers):
    resp = await client.get("/api/v1/nutrition/search?q=rice", headers=auth_headers)
    assert resp.status_code == 200


async def test_cycle_phase_no_date(client, auth_headers):
    resp = await client.get("/api/v1/nutrition/cycle-phase", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["phase"] == "unknown"


async def test_daily_goals(client, auth_headers):
    resp = await client.get("/api/v1/nutrition/daily-goals", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "daily_calorie_goal" in data


# ── Health ────────────────────────────────────────────────────────────────────

async def test_health_endpoint(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
