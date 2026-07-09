# 📄 Bulk Marksheet OCR & Eligibility Screening System

A production-ready, full-stack system designed for bulk OCR processing of academic marksheets (PDF/JPG/PNG/ZIP), automatic PCM cutoff calculation, eligibility screening, and human review workflow. 

This repository has been optimized for **12x faster CPU processing**, robust **CBSE/State Board table alignment**, and features a modern single-page interface with a customizable **Auto/Manual Approval Mode**.

---

## 🏗️ Architecture

```
┌─────────────┐    HTTP     ┌─────────────────┐    Celery    ┌──────────────┐
│  React + TS │ ──────────► │  FastAPI Backend │ ──────────► │ OCR Workers  │
│  Dashboard  │             │  REST API        │             │ (PaddleOCR)  │
└─────────────┘             └────────┬────────┘             └──────┬───────┘
                                     │                              │
                              ┌──────▼──────┐              ┌───────▼──────┐
                              │ PostgreSQL  │              │    Redis     │
                              │ Database    │              │ Broker/Cache │
                              └─────────────┘              └──────────────┘
```

---

## ⚡ Key Optimizations & Features

### 🚀 12x OCR Acceleration (Auto-Rescaling)
Large megapixel images (e.g. 6000x4000) are automatically downscaled to a max-side resolution of `1800px` before passing to PaddleOCR. The extracted coordinates are then mathematically mapped back to the original aspect ratio. This yields a **12x speedup on CPU** (reducing processing from 60 seconds to ~5 seconds per image) while preserving pixel-perfect alignment for UI bounding boxes.

### 📐 Dynamic Table Alignment (Height-Based Tolerance)
Instead of static pixel vertical thresholds, row grouping in [`layout_analyzer.py`](backend/app/core/layout_analyzer.py) uses a **Dynamic Height-Based Tolerance** calculated as `45%` of the text line heights in the row. This ensures robust and accurate marks extraction for tilted, zoomed, high-res, or low-res scanned CBSE and State Board marksheets.

### ⚡ Auto / Manual Approval Toggle
A premium toggle pill in the results header allows switching approval modes instantly:
* **Auto Mode**: Bypasses the ambiguous `REVIEW_REQUIRED` state. Candidates with a computed PCM average above the threshold (e.g. `> 50%`) are automatically marked **`ELIGIBLE`**, otherwise **`NOT_ELIGIBLE`**.
* **Manual Mode**: Ambiguous uploads, missing subjects, or low-confidence lines are flagged as **`REVIEW_REQUIRED`** to request human verification.
* *Note: Manual overrides saved in the review interface are always respected in both modes.*

---

## 🚀 Quick Start (Docker Compose)

### Prerequisites
- Docker Desktop ≥ 24.0
- Docker Compose ≥ 2.20

### 1. Configure Environment
Copy the example variables file to the root `.env`:
```bash
cp .env.example .env
```

### 2. Start Services
```bash
docker compose up --build
```
This starts:
* **Frontend**: [http://localhost:3000](http://localhost:3000) (Vite React app)
* **Backend API**: [http://localhost:8000](http://localhost:8000) (FastAPI app)
* **Swagger API Docs**: [http://localhost:8000/api/docs](http://localhost:8000/api/docs)
* **Celery Worker**: Background document processing worker
* **Redis**: Broker/Cache (port 6379)
* **PostgreSQL**: Database (port 5432)

### 3. Run Database Migrations
```bash
docker compose exec backend alembic upgrade head
```

---

## 💻 Local Development (without Docker)

### Backend Setup
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a Python virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy the environment variables:
   ```bash
   cp ../.env.example .env
   ```
5. Apply database migrations:
   ```bash
   alembic upgrade head
   ```
6. Start the API server:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
7. Start the Celery worker (in a separate terminal):
   ```bash
   export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
   celery -A app.celery_app.celery worker --loglevel=info --concurrency=2 -Q documents,batches
   ```

### Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install npm packages:
   ```bash
   npm install
   ```
3. Start the Vite development server:
   ```bash
   npm run dev
   ```

---

## 📋 Core API Endpoints

| Method | Endpoint                        | Description                       |
|--------|---------------------------------|-----------------------------------|
| POST   | `/api/batches`                  | Create a new screening batch      |
| POST   | `/api/batches/{id}/upload`      | Upload files (supports ZIP / PDF) |
| GET    | `/api/batches/{id}/results`     | Paginated document results        |
| GET    | `/api/batches/{id}/export/xlsx` | Export results as Excel sheet     |
| GET    | `/api/documents/{id}/review`    | Retrieve review panel data        |
| PUT    | `/api/documents/{id}/review`    | Submit manual verification        |
| POST   | `/api/documents/{id}/reprocess` | Re-enqueue document for OCR       |

---

## ⚙️ Configuration (.env)

| Variable | Default | Description |
|---|---|---|
| `CUTOFF_FORMULA` | `pcm_average` | `pcm_average` or `engineering_200` |
| `MATH_MODE` | `combined` | `combined` (weighted) or `simple_average` |
| `ELIGIBILITY_THRESHOLD` | `50.0` | Strict greater-than (> threshold) eligibility limit |
| `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK` | `True` | Disables Paddle model server integrity source checks |

---

## 📁 Project Structure

```
ocr-system/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app setup
│   │   ├── config.py            # Settings and variables
│   │   ├── database.py          # SQLAlchemy engine setup
│   │   ├── api/                 # API routers
│   │   ├── core/                # Core pipeline, OCR, cutoff, export generators
│   │   └── tasks/               # Celery async tasks
│   └── migrations/              # Alembic migrations database schema
├── frontend/
│   ├── src/
│   │   ├── pages/               # Dashboard and main screening screens
│   │   ├── components/          # ProgressBar, badge elements
│   │   └── api/                 # Axios client API hooks
│   └── package.json
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 🤝 Brand Details
* **Admin Brand Logo**: "V" Minimal Branding
* **App Footer**: `"Viggu - Lazy but Smart"` with standard authority details
* **General Style**: Premium glassmorphism light interface
