# Household Finances

Angular frontend and FastAPI backend for a shared household finance application.

Project requirements, decisions, and test evidence are documented in [Project Context](context/README.md).

## Requirements

- Node.js 22.12 or newer in the 22.x line
- Python 3.12
- Docker Compose for the local PostgreSQL service

## Start PostgreSQL

From the repository root:

```powershell
docker compose up -d db
```

The local database uses development-only credentials from `compose.yaml`. Do not reuse them outside local development. The configured port is published on all host interfaces, so network access depends on your firewall; this setup is not intended for production.

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

Open `http://localhost:4200`. The page shows the monthly household ledger: a month selector, the combined income, household expenses and remaining balance, each partner's income, a form to add an expense, and that month's expenses. The footer reports whether the API liveness endpoint is reachable.

## Tests

From `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Backend tests migrate a temporary SQLite database by default. To run the same tests against PostgreSQL, create a dedicated database once and point `TEST_DATABASE_URL` at it. Each test migrates that database and then downgrades it to empty, so never use the development database here.

```powershell
docker compose exec db createdb -U household household_finances_test
$env:TEST_DATABASE_URL = "postgresql+psycopg://household:household_dev@localhost:5432/household_finances_test"
.\.venv\Scripts\python.exe -m pytest
Remove-Item Env:\TEST_DATABASE_URL
```

From `frontend`:

```powershell
npm test -- --watch=false
npm run build
```

## Health endpoints

- `GET /health/live` reports that the API process is responsive.
- `GET /health/ready` checks database connectivity and returns a sanitized `503` response when PostgreSQL is unavailable.

## Ledger endpoints

Amounts are EUR decimal strings with up to two decimals, for example `"12.36"`. Months use `YYYY-MM`.

| Endpoint | Purpose |
| --- | --- |
| `GET /categories` | Expense categories with their subcategories. |
| `GET /members` | The two household partners. |
| `PATCH /members/{id}` | Change a partner's label. |
| `POST /expenses` | Record a household expense with `transaction_date`, `amount`, `category_id` and optional `subcategory_id`. |
| `GET /expenses?month=` | Expenses whose transaction date falls in the month. |
| `POST /incomes` | Record a partner's income for a month with `member_id`, `month` and `amount`; one per partner per month. |
| `GET /incomes?month=` | Incomes recorded for the month. |
| `GET /summary?month=` | Each partner's income, combined income, combined expenses and remaining balance. |
| `PUT /budgets/{category_id}?month=YYYY-MM` | Set or update a category budget for a month. |

Errors use `{"detail": {"code", "message", "errors"?}}`: `422 invalid_input` for invalid values, `404 not_found`, `409 conflict` for a second income for the same partner and month, and a sanitized `503 database_unavailable` when storage fails. A failed write is rolled back.
