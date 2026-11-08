# Household Finances

Angular frontend and FastAPI backend for a shared household finance application.

## Requirements

- Node.js 22.12 or newer in the 22.x line
- Python 3.12
- Docker Compose for the local PostgreSQL service

## Start PostgreSQL

From the repository root:

```powershell
docker compose up -d db
```

The local database uses development-only credentials from `compose.yaml`. Do not reuse them outside local development.

## Start the API

```powershell
Set-Location backend
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\uvicorn.exe app.main:app --reload
```

The API is available at `http://localhost:8000`. Interactive OpenAPI documentation is at `http://localhost:8000/docs`.

## Start the frontend

In a second terminal from the repository root:

```powershell
Set-Location frontend
npm ci
npm start
```

Open `http://localhost:4200`. The development screen checks the API liveness endpoint and reports whether it is reachable.

## Tests

From `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

From `frontend`:

```powershell
npm test -- --watch=false
npm run build
```

## Health endpoints

- `GET /health/live` reports that the API process is responsive.
- `GET /health/ready` checks database connectivity and returns a sanitized `503` response when PostgreSQL is unavailable.
