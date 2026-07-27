# Open Antibiotic Discovery

An initial research workspace for ranking antimicrobial compounds with traceable
evidence and explicit uncertainty. This repository is a foundation, not a
validated drug-discovery system.

## Architecture

- `backend/`: FastAPI, SQLAlchemy, Pydantic, and pytest
- `frontend/`: React, TypeScript, Vite, and Vitest
- `docker-compose.yml`: PostgreSQL for development

SQLite is the backend default so the first run does not require Docker.

## Quick start

### Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e "./backend[dev]"
uvicorn app.main:app --app-dir backend --reload
```

The API is available at `http://localhost:8000`; interactive documentation is
at `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

### Tests

```bash
pytest backend/tests
cd frontend && npm test
```

## PostgreSQL

```bash
docker compose up -d db
export DATABASE_URL=postgresql+psycopg://antibiotics:antibiotics@localhost:5432/antibiotics
```

The API creates its initial tables on startup. Add Alembic migrations before
the schema begins changing in shared environments.

## Scientific boundary

Scores in the seed data are illustrative. Predictions must retain dataset,
model, split, calibration, and experiment provenance before they can support
scientific decisions.

