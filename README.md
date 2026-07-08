# 📄 Bulk Marksheet OCR & Eligibility Screening System

A production-ready full-stack system for batch OCR processing of academic marksheets (PDF/JPG/PNG), automatic PCM cutoff calculation, eligibility screening, and human review workflow.

---

## 🏗️ Architecture

```
┌─────────────┐    HTTP     ┌─────────────────┐    Celery    ┌──────────────┐
│  React + TS │ ──────────► │  FastAPI Backend │ ──────────► │ OCR Workers  │
│  Dashboard  │             │  REST API        │             │ (PaddleOCR)  │
└─────────────┘             └────────┬────────┘             └──────┬───────┘
                                     │                              │
                              ┌──────▼──────┐              ┌───────▼──────┐
                              │ PostgreSQL   │              │    Redis      │
                              │ Database     │              │ Broker/Cache  │
                              └─────────────┘              └──────────────┘
```

## 🚀 Quick Start (Docker)

### Prerequisites
- Docker Desktop ≥ 24
- Docker Compose ≥ 2.20

### 1. Clone and Configure

```bash
git clone <repo-url>
cd ocr-system
cp .env.example .env
# Edit .env if needed (defaults work for local development)
```

### 2. Start All Services

```bash
docker compose up --build
```

This starts:
| Service   | URL                    | Description              |
|-----------|------------------------|--------------------------|
| Frontend  | http://localhost:3000  | React admin dashboard    |
| Backend   | http://localhost:8000  | FastAPI REST API         |
| API Docs  | http://localhost:8000/api/docs | Swagger UI        |
| Flower    | http://localhost:5555  | Celery task monitor      |
| Redis     | localhost:6379         | Message broker           |
| Postgres  | localhost:5432         | Database                 |

### 3. Run Database Migrations

```bash
# Inside running backend container:
docker compose exec backend alembic upgrade head

# Or from host (with Python virtualenv):
cd backend
alembic upgrade head
```

---

## 💻 Local Development (without Docker)

### Backend Setup

```bash
cd backend

# Create virtualenv
python3.11 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp ../.env.example .env
# Edit DATABASE_URL, REDIS_URL etc. for local connections

# Apply migrations
alembic upgrade head

# Start API server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Start Celery worker (separate terminal)
celery -A app.celery_app.celery worker --loglevel=info --concurrency=4 -Q documents,batches
```

### Frontend Setup

```bash
cd frontend

npm install
npm run dev
# Opens at http://localhost:3000
```

---

## 🧪 Running Tests

```bash
cd backend

# Run all tests
pytest tests/ -v

# Run specific test files
pytest tests/test_eligibility.py -v
pytest tests/test_math_special.py -v
pytest tests/test_subject_normalizer.py -v
pytest tests/test_validator.py -v

# With coverage report
pytest tests/ --cov=app --cov-report=html
```

---

## 📋 API Endpoints

| Method | Endpoint                                | Description                    |
|--------|-----------------------------------------|--------------------------------|
| POST   | `/api/batches`                          | Create a new batch             |
| POST   | `/api/batches/{id}/upload`              | Upload 1–1000 files to batch   |
| GET    | `/api/batches`                          | List all batches               |
| GET    | `/api/batches/{id}`                     | Get batch details              |
| GET    | `/api/batches/{id}/progress`            | Real-time progress             |
| GET    | `/api/batches/{id}/results`             | Paginated document results     |
| GET    | `/api/batches/{id}/export/csv`          | Export results as CSV          |
| GET    | `/api/batches/{id}/export/xlsx`         | Export results as Excel        |
| GET    | `/api/documents/{id}`                   | Get document details           |
| GET    | `/api/documents/{id}/ocr`               | Get OCR tokens                 |
| GET    | `/api/documents/{id}/review`            | Get full review data           |
| PUT    | `/api/documents/{id}/review`            | Submit manual review           |
| POST   | `/api/documents/{id}/reprocess`         | Requeue for reprocessing       |

---

## ⚙️ Configuration

Key environment variables (see `.env.example`):

| Variable                        | Default          | Description                         |
|---------------------------------|------------------|-------------------------------------|
| `CUTOFF_FORMULA`                | `pcm_average`    | `pcm_average` or `engineering_200`  |
| `MATH_MODE`                     | `combined`       | `combined` or `simple_average`      |
| `ELIGIBILITY_THRESHOLD`         | `50.0`           | Strict > threshold (not >=)         |
| `OCR_CONFIDENCE_AUTO_THRESHOLD` | `0.90`           | Auto-approve above this confidence  |
| `OCR_CONFIDENCE_REVIEW_THRESHOLD`| `0.75`          | Route to review below this          |
| `PADDLEOCR_USE_GPU`             | `false`          | Enable GPU for faster OCR           |
| `MAX_FILE_SIZE_MB`              | `50`             | Max file size per upload            |
| `CELERY_CONCURRENCY`            | `4`              | Parallel OCR workers                |

---

## 🔄 Processing Pipeline

```
Upload Files
  → Validate (size, extension, MIME)
  → Duplicate detection (SHA-256 hash)
  → Store file + Create Document record
  → Queue Celery task per document
  → Detect PDF type (native text vs scanned)
  → Extract native text OR render to image
  → Preprocess image (rotate, deskew, CLAHE, denoise, perspective)
  → Run PaddleOCR (text + bbox + confidence per token)
  → Spatial layout analysis (group tokens into table rows)
  → Subject normalization (exact aliases + RapidFuzz fuzzy)
  → Marks extraction (obtained + maximum per subject)
  → Validation (numeric checks, bounds, duplicates, suspicious chars)
  → Cutoff calculation (PCM average or Engineering 200)
  → Eligibility determination (strict >50% all subjects)
  → Confidence scoring → route to auto/review
  → Persist to PostgreSQL
  → Update batch progress counters
```

---

## 🎯 Eligibility Rules

A candidate is **ELIGIBLE** only when **ALL** of:
- Physics > 50%
- Chemistry > 50%  
- Mathematics > 50%
- Overall > 50%

**Note**: Exactly 50% is **NOT eligible** (strict greater-than).

Any missing subject or low confidence → **REVIEW_REQUIRED** (never auto-eligible/ineligible).

---

## 📁 Project Structure

```
ocr-system/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app
│   │   ├── config.py            # Settings
│   │   ├── database.py          # SQLAlchemy async engine
│   │   ├── celery_app.py        # Celery configuration
│   │   ├── schemas.py           # Pydantic models
│   │   ├── models/              # SQLAlchemy ORM models
│   │   ├── api/                 # FastAPI routers
│   │   ├── core/                # Core pipeline modules
│   │   └── tasks/               # Celery tasks
│   ├── migrations/              # Alembic migrations
│   ├── tests/                   # pytest test suite
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/               # React pages
│   │   ├── components/          # Reusable components
│   │   ├── api/                 # API client
│   │   ├── types.ts             # TypeScript types
│   │   └── utils.ts             # Utilities
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 📊 Sample Test Data Format

For testing, prepare marksheets with the following structure:

```
Candidate Name: John Doe
Register Number: 123456789

Subject         | Obtained | Maximum
----------------|----------|--------
Physics         |   75     |  100
Chemistry       |   80     |  100
Mathematics     |   70     |  100
Total           |  225     |  300
```

Supported formats: PDF (native text or scanned), JPG, JPEG, PNG.

---

## 🐛 Troubleshooting

**PaddleOCR model download fails in Docker:**
```bash
# Pre-download models inside container
docker compose exec worker python -c "from paddleocr import PaddleOCR; PaddleOCR(use_angle_cls=True, lang='en')"
```

**Database connection errors:**
```bash
# Check PostgreSQL is healthy
docker compose ps
docker compose logs db
```

**Celery workers not processing:**
```bash
# Check worker logs
docker compose logs worker

# Monitor via Flower
open http://localhost:5555
```

**GPU acceleration (optional):**
```bash
# Set in .env
PADDLEOCR_USE_GPU=true
# Ensure NVIDIA Docker runtime is installed
```
