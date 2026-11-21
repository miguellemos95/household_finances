# Household Finances

Angular frontend and FastAPI backend for a shared household finance application.

Project requirements, decisions, and test evidence are documented in [Project Context](context/README.md).

## Requirements

- Node.js 22.12 or newer in the 22.x line
- Python 3.12
- Docker Compose for the local PostgreSQL service

## Run locally (Windows PowerShell)

Start Docker Desktop, then open a PowerShell terminal in the project root (the directory containing `compose.yaml`). Start PostgreSQL:

```powershell
docker compose up -d db
```

The local database uses development-only credentials from `compose.yaml`. Do not reuse them outside local development. The configured port is published on all host interfaces, so network access depends on your firewall; this setup is not intended for production.

### Start the API

Open a second PowerShell terminal in the project root. On the first run, create the virtual environment and install dependencies:

```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

In the same terminal, apply migrations and start the API:

```powershell
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\uvicorn.exe app.main:app --reload
```

On later runs, open a terminal in the project root and run `Set-Location backend` before the migration and API commands. The defaults connect to the local Compose database; to override them, copy `backend\.env.example` to `backend\.env` and adjust the settings.

The API is available at [http://localhost:8000](http://localhost:8000). Interactive API documentation is at [http://localhost:8000/docs](http://localhost:8000/docs).

### Start the frontend

Open a third PowerShell terminal in the project root. On the first run, install dependencies, then start Angular:

```powershell
Set-Location frontend
npm ci
npm start
```

On later runs, use `Set-Location frontend` and `npm start`; `npm ci` is only needed when dependencies need to be installed or restored.

Open [http://localhost:4200](http://localhost:4200). The page shows the monthly household ledger, income and expense forms, bills, and category budgets. The footer reports whether the API is reachable.

Press **Ctrl+C** in the API and frontend terminals to stop them. To stop PostgreSQL, run `docker compose stop db` from the project root; its data remains in the Docker volume.

### Optional: add sample budget data

With the API running, use another PowerShell terminal to add example data for the current month:

```powershell
$api = 'http://localhost:8000'
$month = Get-Date -Format 'yyyy-MM'
$today = Get-Date -Format 'yyyy-MM-dd'

Invoke-RestMethod -Method Put -Uri "$api/budgets/1?month=$month" -ContentType 'application/json' -Body '{"amount":"300.00"}'
Invoke-RestMethod -Method Put -Uri "$api/budgets/2?month=$month" -ContentType 'application/json' -Body '{"amount":"150.00"}'
Invoke-RestMethod -Method Post -Uri "$api/expenses" -ContentType 'application/json' -Body "{`"transaction_date`":`"$today`",`"amount`":`"245.00`",`"category_id`":1,`"subcategory_id`":1}"
Invoke-RestMethod -Method Post -Uri "$api/expenses" -ContentType 'application/json' -Body "{`"transaction_date`":`"$today`",`"amount`":`"180.00`",`"category_id`":2,`"subcategory_id`":null}"
```

These commands use the default seeded category IDs and write to the local development database. They overwrite existing budgets for those categories and add expenses each time they are run. On a fresh database they show a warning for Bills and an over-budget state for Groceries; existing expenses affect the results.

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
| `POST /bills` | Create a one-off or monthly bill with a due date, amount, category and optional subcategory. |
| `GET /bills?month=YYYY-MM` | Show occurrences due in the month, earlier unpaid occurrences, and occurrences paid in the month. |
| `PUT /bills/occurrences/{id}/amount` | Adjust an unpaid occurrence's amount. |
| `POST /bills/occurrences/{id}/pay` | Mark an occurrence paid with its actual `paid_amount` and `paid_date`; creates one household expense on that date. |

Errors use `{"detail": {"code", "message", "errors"?}}`: `422 invalid_input` for invalid values, `404 not_found`, `409 conflict` for a duplicate income or an attempt to pay or adjust a paid bill, and a sanitized `503 database_unavailable` when storage fails. A failed write is rolled back.
