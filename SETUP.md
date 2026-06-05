# Nutrition Vision — Setup Guide

A plain-English walkthrough of every component and what you need to do to run the app.

---

## What is this?

Nutrition Vision is an app where you take a photo of your meal and it tells you:
- What foods are in it (detected by AI)
- How much of each food (estimated from the image depth)
- The calories, protein, carbs, fat, and fibre
- Hidden ingredients like ghee or cream that weren't visible
- Personalised tips based on your fitness goal and cycle phase

---

## The big picture

```
Your phone (React Native app)
        ↓  takes photo, sends to:
Backend API  (FastAPI / Python)
        ↓  puts job in queue
Redis        (job queue)
        ↓  Celery worker picks it up
ML Pipeline  (YOLOv8 → SAM2 → Depth AI → Claude)
        ↓  saves result to
PostgreSQL   (permanent storage)
        ↑  phone polls until done
```

---

## Folder structure explained

```
nutrition-vision/
│
├── backend/               ← Python server (the "brain")
│   ├── app/
│   │   ├── main.py        ← Starting point of the API server
│   │   ├── config.py      ← All settings (reads from .env file)
│   │   ├── routers/       ← API endpoints (what the app can call)
│   │   │   ├── analysis.py   → /analysis — submit photo, poll result
│   │   │   ├── meals.py      → /meals — save & view meal history
│   │   │   ├── users.py      → /users, /auth — login, register, profile
│   │   │   ├── nutrition.py  → /nutrition — food search, cycle phase, daily goals
│   │   │   └── coaching.py   → /coaching — weekly AI summary
│   │   ├── models/        ← Database table definitions
│   │   ├── services/      ← Business logic (cycle calc, goals, S3)
│   │   ├── tasks/         ← Background jobs (Celery)
│   │   └── core/          ← Shared utilities (logging, Redis job store)
│   ├── alembic/           ← Database migration scripts
│   └── tests/             ← Automated tests
│
├── nutrition_engine/      ← The AI pipeline (the "eyes")
│   ├── pipeline.py        ← Orchestrates all 9 stages
│   ├── detector.py        ← YOLOv8: finds food in the photo
│   ├── secondary_classifier.py  ← EfficientNet: double-checks uncertain detections
│   ├── segmentor.py       ← SAM2: draws a precise outline around each food
│   ├── depth_estimator.py ← Depth Anything v2: estimates how tall/deep each food is
│   ├── volume_calculator.py    ← Converts depth map into estimated ml
│   ├── gram_converter.py  ← Converts ml → grams using food density tables
│   ├── nutrition_lookup.py ← Looks up calories/macros (IFCT → USDA → fallback)
│   ├── llm_validator.py   ← Claude: validates results, finds hidden ingredients
│   └── density_tables/    ← JSON files with nutrition data (~50 Indian + global foods)
│
├── frontend/              ← React Native mobile app (what you see on your phone)
│   ├── app/               ← Screens (Expo Router file-based routing)
│   │   ├── (tabs)/        ← Main 4 tabs: Camera, History, Insights, Profile
│   │   ├── analysis/      ← Analysis result screen + portion confirmation
│   │   ├── meals/         ← Meal detail screen
│   │   └── onboarding/    ← Login / Register screens
│   ├── components/        ← Reusable UI pieces (macro ring chart, food chips, etc.)
│   ├── hooks/             ← Data-fetching logic (useAnalysis, useMealHistory)
│   ├── store/             ← Auth token storage (Zustand + SecureStore)
│   └── services/api.ts    ← All API calls in one place
│
├── training/              ← Scripts to train the AI models (optional)
│   ├── scripts/           ← train_detector.py, train_classifier.py, etc.
│   └── notebooks/         ← Jupyter notebooks for data exploration
│
├── models/weights/        ← Where trained model files go (not in git)
│
├── docker-compose.yml     ← Runs everything locally with one command
├── docker-compose.prod.yml ← Production version (adds HTTPS via nginx)
├── Makefile               ← Shortcuts (make dev, make test, etc.)
├── .env.example           ← Template for your settings
└── scripts/quickstart.sh  ← Automated first-time setup
```

---

## Step 1 — Install prerequisites

You need these installed on your computer:

| Tool | What it does | Download |
|------|-------------|----------|
| **Docker Desktop** | Runs the server stack in containers | https://docs.docker.com/get-docker/ |
| **Node.js 20+** | Runs the React Native / Expo build tools | https://nodejs.org |
| **Python 3.11+** | Only needed if you want to run training scripts locally | https://python.org |
| **Expo Go app** | Install on your phone to preview the app | App Store / Play Store |

---

## Step 2 — Get API keys

The app needs two API keys. Both have free tiers that are fine for development.

### Anthropic API key (required for AI coaching and hidden ingredient detection)
1. Go to https://console.anthropic.com
2. Sign up / log in
3. Click **API Keys** → **Create Key**
4. Copy the key — it starts with `sk-ant-`

### USDA FoodData Central API key (optional — improves food database coverage)
1. Go to https://fdc.nal.usda.gov/api-key-signup.html
2. Fill in the form — the key arrives by email instantly
3. Copy the key

---

## Step 3 — Configure your environment

```bash
# 1. Go into the project folder
cd "nutrition-vision"

# 2. Copy the template
cp .env.example .env

# 3. Open .env in any text editor and fill in:
#    ANTHROPIC_API_KEY=sk-ant-your-key-here
#    USDA_API_KEY=your-usda-key-here
#    SECRET_KEY=any-long-random-string   ← used to sign login tokens
```

Everything else in `.env` has sensible defaults for local development.

---

## Step 4 — Start the backend

```bash
# From the nutrition-vision/ folder:
bash scripts/quickstart.sh
```

This script:
1. Creates a `.env` file (if missing) with a random `SECRET_KEY`
2. Builds the Docker images
3. Starts Postgres and Redis
4. Runs database migrations (creates tables)
5. Starts the API server and Celery worker
6. Prints the URLs when ready

**When it's done you'll see:**
```
API:              http://localhost:8000
Interactive docs: http://localhost:8000/docs
Celery dashboard: http://localhost:5555
```

The interactive docs at `/docs` let you test every API endpoint directly in your browser — no mobile app needed.

---

## Step 5 — Start the mobile app

```bash
cd frontend
npm install          # installs all JavaScript packages (first time only)
npx expo start       # starts the Expo dev server
```

Then:
- **On your phone**: Open the **Expo Go** app and scan the QR code
- **On a simulator**: Press `i` for iOS simulator or `a` for Android emulator

> **Important**: Your phone and computer must be on the same Wi-Fi network for Expo Go to work.
> If it doesn't connect, set `EXPO_PUBLIC_API_URL=http://YOUR_COMPUTER_IP:8000` in `frontend/.env.local`.

---

## Step 6 — Try it

1. Open the app and register an account
2. Set your profile (weight, height, goal)
3. Optionally set your last period date for cycle-aware tips
4. Tap the camera tab, take a photo of any food
5. Watch the analysis run (usually 10–30 seconds without GPU)
6. See the breakdown!

The **History** tab shows all your past meals.
The **Insights** tab shows a 7-day calorie chart and your current cycle phase card.
The **Profile** tab shows your daily goals.

---

## Running the AI models (optional — makes results much more accurate)

Without trained model weights, the app uses **mock fallbacks** that return a fixed list of foods ("rice", "dal") so you can test the full app flow. To get real detections:

### Option A — Use pre-trained weights (recommended)
```bash
# Download YOLOv8 nano (general object detection, ~6 MB)
make download-models
```
This downloads a base YOLOv8 model. It knows 80 COCO object classes but not food specifically — accuracy will be moderate.

### Option B — Train on Food-101 (best accuracy, needs ~4 hours + GPU)
```bash
# Download Food-101 dataset (~5 GB)
make datasets

# Train YOLOv8 food detector
make train-detector

# Train EfficientNet-B3 secondary classifier
# (edit training/scripts/train_classifier.py to set your epochs/batch size first)
python training/scripts/train_classifier.py
```

After training, weights land in `models/weights/` and the pipeline picks them up automatically on next restart.

---

## Deploying to production

```bash
# Copy .env.example to .env.prod and fill in production values
# Make sure POSTGRES_PASSWORD is a real password

docker-compose -f docker-compose.prod.yml up -d
```

The production compose file adds:
- **nginx** with HTTPS (you need to add your SSL certificates to `nginx/certs/`)
- Rate limiting (30 requests/minute on the analysis endpoint)
- `alembic upgrade head` runs automatically before the API starts

---

## Common problems

### "No food detected" on every photo
The ML models aren't loaded — you're seeing mock results. Either run `make download-models` or the worker logs will tell you which weights file is missing.

### App can't connect to the API
- Make sure Docker is running: `docker-compose ps`
- Check API logs: `docker-compose logs api`
- On Expo Go, make sure `EXPO_PUBLIC_API_URL` points to your computer's IP, not `localhost`

### Database migrations fail
```bash
docker-compose run --rm api alembic upgrade head
```
Check that Postgres is running first: `docker-compose ps postgres`

### Celery worker keeps crashing
```bash
docker-compose logs worker
```
Usually the worker crashes if `ANTHROPIC_API_KEY` is set to an invalid value. It will still work — Claude calls have try/except fallbacks — but check the logs for the actual error.

### "Image blurry" error
The blur detector (Laplacian variance) rejected the image. Move closer to the food, make sure the lighting is good, and hold the phone steady.

---

## Making changes

### Backend changes
Edit any Python file in `backend/` — the API server reloads automatically because docker-compose runs uvicorn with `--reload`.

### Frontend changes
Edit any file in `frontend/` — Expo hot-reloads automatically.

### Adding a new food to the nutrition database
Edit `nutrition_engine/density_tables/embedded_nutrition.json`.  
Each entry looks like:
```json
"dal_makhani": {
  "calories": 150,
  "protein_g": 7.2,
  "carbs_g": 16.5,
  "fat_g": 6.8,
  "fiber_g": 3.1,
  "serving_g_min": 100,
  "serving_g_max": 300,
  "source": "IFCT 2017"
}
```
Restart the worker after editing: `docker-compose restart worker`

---

## Architecture decisions worth knowing

**Why Redis for jobs?** When you submit a photo, the API returns a `job_id` immediately (202 Accepted). The actual ML processing happens in a separate Celery worker process. Redis is the message broker and also stores job status so you can poll for results. This means the API never blocks waiting for slow ML inference.

**Why two separate Docker services (api + worker)?** So you can scale them independently. If analysis is slow, add more workers. The API stays fast.

**Why IFCT instead of USDA for Indian foods?** USDA doesn't have accurate data for Indian dishes — it has "dal" but with wrong calorie values for the way Indians cook it. IFCT (Indian Food Composition Tables, 2017) is the government standard reference.

**Why Claude for validation?** Claude knows that roti always has ghee, dal makhani has butter and cream, and biryani has hidden oil. The vision models detect visible food but miss ingredients absorbed during cooking. Claude adds ~100–150 kcal of accuracy for Indian meals.

**Why EfficientNet as a secondary classifier?** YOLOv8 is great at detecting where food is (bounding boxes) but its confidence on specific Indian food labels can be low because it was trained mostly on Western foods. When YOLO confidence < 0.6, EfficientNet (trained on Food-101) gets a second vote on the label.
