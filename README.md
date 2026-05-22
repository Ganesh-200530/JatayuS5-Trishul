# AutoAuthAgent

Autonomous Prior Authorization Platform — automates PA from clinical evidence extraction through submission and appeals using Gemini LLM.

## Quick Start

### 1. Prerequisites
- Python 3.12+
- PostgreSQL 16+
- Google Gemini API key

### 2. Setup

```bash
# Clone and enter project
cd MEDIX

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env
# Edit .env with your GEMINI_API_KEY and database credentials
```

### 3. Database

**Option A — Docker (recommended):**
```bash
docker compose up db -d
```

**Option B — Local PostgreSQL:**
```sql
CREATE DATABASE autoauth;
CREATE USER autoauth WITH PASSWORD 'autoauth';
GRANT ALL PRIVILEGES ON DATABASE autoauth TO autoauth;
```

### 4. Run

```bash
# Start the server (auto-creates tables in dev mode)
uvicorn app.main:app --reload

# Seed sample data (policies, users)
python -m scripts.seed
```

### 5. Access

- **API Docs:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **Health Check:** http://localhost:8000/health

### 6. Docker (full stack)

```bash
# Set your Gemini key
$env:GEMINI_API_KEY="your-key-here"

docker compose up --build
```

## API Overview

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/auth/register` | POST | Register a new user |
| `/api/v1/auth/login` | POST | Login, get JWT token |
| `/api/v1/patients/` | POST/GET | Create/list patients |
| `/api/v1/prior-auth/` | POST | Create PA request → triggers full pipeline |
| `/api/v1/prior-auth/{id}` | GET | Get PA status & details |
| `/api/v1/prior-auth/{id}/evidence` | GET | Get extracted clinical evidence |
| `/api/v1/prior-auth/{id}/retry` | POST | Retry failed pipeline |
| `/api/v1/appeals/` | POST | Initiate appeal for denied PA |
| `/api/v1/policies/` | POST/GET | Manage payer policies & criteria |
| `/api/v1/dashboard/stats` | GET | Aggregate PA statistics |

## Architecture

```
POST /prior-auth → Orchestrator
    → Clinical Reader Agent (Gemini: extract evidence from notes)
    → Policy Agent (Gemini: gap analysis vs payer criteria)
    → Submission Agent (FHIR PAS $submit to payer)
    → If denied: Appeal Agent (Gemini: draft appeal letter)
    → If low confidence: escalate to human reviewer
```

## Project Structure

```
app/
├── main.py                 # FastAPI app entry point
├── config.py               # Settings (env vars)
├── database.py             # SQLAlchemy async engine
├── models/                 # Database models
│   ├── patient.py
│   ├── prior_auth.py
│   ├── clinical_evidence.py
│   ├── policy.py
│   ├── submission.py
│   ├── appeal.py
│   ├── audit.py
│   └── user.py
├── schemas/                # Pydantic request/response models
├── api/
│   ├── router.py           # Route aggregation
│   └── endpoints/          # REST endpoints
├── agents/
│   ├── orchestrator.py     # Workflow coordinator
│   ├── clinical_reader.py  # Evidence extraction agent
│   ├── policy_agent.py     # Policy gap analysis agent
│   ├── submission_agent.py # PA submission agent
│   └── appeal_agent.py     # Denial appeal agent
├── services/
│   ├── gemini.py           # Gemini LLM integration
│   ├── fhir.py             # FHIR R4 client
│   └── audit.py            # Audit logging
└── core/
    ├── security.py         # JWT auth, password hashing
    ├── exceptions.py       # Custom HTTP exceptions
    └── middleware.py        # Request logging
```
