# NutriVision — AI Meal Analysis App

Snap a photo of your meal and get an instant full nutrition breakdown, blood sugar impact prediction, and personalised wellness insights.

## Features

- **AI Food Detection** — Claude Vision identifies every food item in the photo, including hidden ingredients like cooking oil and butter
- **Full Macro Breakdown** — calories, protein, carbs, fat, fibre per item and total
- **Blood Sugar Impact** — estimates glycaemic load with fibre/protein/fat buffer model, scored Low / Moderate / High
- **Portion Adjustment** — confirm and tweak portion sizes before saving
- **Meal History** — full log with daily and weekly nutrition summaries
- **Female Wellness** — cycle phase tracking with personalised calorie and nutrient targets
- **AI Coaching** — weekly summaries and recommendations based on eating patterns

## Tech Stack

**Frontend**
- React Native + Expo (SDK 54)
- Expo Router v6 (file-based navigation)
- TanStack React Query v4
- Zustand (auth + state)

**Backend**
- FastAPI (async Python)
- Celery + Redis (async job queue)
- PostgreSQL + SQLAlchemy + Alembic
- Claude Vision API (food detection & nutrition estimation)
- USDA / IFCT nutrition databases

**Infrastructure**
- Docker Compose
- AWS S3 (image storage)
- Cloudflare Tunnel (dev)

## How It Works

1. User takes a photo → uploaded to S3
2. Celery worker picks up the job
3. Claude Vision identifies food items, estimates grams and nutrition per 100g
4. Hidden ingredients (ghee, oil, butter) are inferred from dish context
5. Glycaemic load is calculated with fibre, protein, and fat buffers applied
6. Result saved to PostgreSQL, status updated in Redis
7. App polls until complete and displays the breakdown

## Setup

```bash
# Clone and configure
cp .env.example .env
# Fill in: DATABASE_URL, REDIS_URL, ANTHROPIC_API_KEY, AWS credentials

# Start all services
docker compose up --build

# Run DB migrations
docker compose exec api alembic upgrade head
```

Frontend:
```bash
cd frontend
npm install
npx expo start
```

## Project Structure

```
├── backend/          # FastAPI app, routers, models, tasks
├── frontend/         # React Native / Expo app
├── nutrition_engine/ # ML pipeline, LLM validator, blood sugar estimator
├── training/         # Model training scripts
└── docker-compose.yml
```
