from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from threading import Barrier
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from httpx import Response
from sqlalchemy import Engine, event, func, select
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from api_client import send
from app.config import Settings
from app.main import create_app
from app.models import Category, Expense, Subcategory

Api = Callable[..., Response]

WORKBOOK_CATEGORIES = [
    ("Bills", ["Water", "Electricity", "Heating", "Home Internet", "Phone Plan"]),
    ("Groceries", []),
    ("Beauty", ["Hairdresser", "Face", "Body", "Hair"]),
    ("Transports", ["Bus", "Spark", "Bolt/Uber"]),
    ("Eat out", ["Restaurants", "Cafe"]),
    ("Clothes", []),
]
# November amounts from the workbook; it has no transaction dates, so these are illustrative.
WORKBOOK_NOVEMBER_EXPENSES = [
    ("2025-11-03", "12.36", "Bills", "Home Internet"),
    ("2025-11-03", "17.97", "Bills", "Phone Plan"),
    ("2025-11-08", "52.89", "Groceries", None),
    ("2025-11-12", "2.99", "Beauty", "Hair"),
    ("2025-11-14", "8.75", "Transports", "Bus"),
    ("2025-11-14", "10.14", "Transports", "Spark"),
    ("2025-11-21", "32.00", "Eat out", "Restaurants"),
    ("2025-11-22", "49.19", "Eat out", "Cafe"),
    ("2025-11-29", "520.94", "Clothes", None),
]
DATABASE_UNAVAILABLE = {
    "detail": {"code": "database_unavailable", "message": "Database is unavailable."}
}


def category_reference(api: Api, category: str, subcategory: str | None = None) -> dict:
    categories = {item["name"]: item for item in api("GET", "/categories").json()}
    selected = categories[category]
    subcategory_id = None
    if subcategory is not None:
        subcategory_id = next(
            item["id"] for item in selected["subcategories"] if item["name"] == subcategory
        )
    return {"category_id": selected["id"], "subcategory_id": subcategory_id}


def record_expense(
    api: Api,
    transaction_date: str,
    amount: str,
    category: str,
    subcategory: str | None = None,
) -> Response:
    payload = {
        "transaction_date": transaction_date,
        "amount": amount,
        **category_reference(api, category, subcategory),
    }
    return api("POST", "/expenses", json=payload)


def member_ids(api: Api) -> dict[str, int]:
    return {member["name"]: member["id"] for member in api("GET", "/members").json()}


def record_income(api: Api, member_name: str, month: str, amount: str) -> Response:
    payload = {"member_id": member_ids(api)[member_name], "month": month, "amount": amount}
    return api("POST", "/incomes", json=payload)


def read_month(api: Api, path: str, month: str):
    response = api("GET", path, params={"month": month})
    assert response.status_code == 200
    return response.json()


def assert_invalid(response: Response, field: str) -> None:
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "invalid_input"
    assert field in [error["field"] for error in detail["errors"]]


@contextmanager
def failing_commits(app: FastAPI) -> Iterator[None]:
    def fail(connection) -> None:
        raise OperationalError("COMMIT", {}, Exception("private storage detail"))

    engine = app.state.database_engine
    event.listen(engine, "commit", fail)
    try:
        yield
    finally:
        event.remove(engine, "commit", fail)


def assert_sanitized_storage_failure(response: Response) -> None:
    assert response.status_code == 503
    assert response.json() == DATABASE_UNAVAILABLE
    assert "private" not in response.text


def test_categories_match_workbook_without_groceries_subcategories(api: Api) -> None:
    response = api("GET", "/categories")

    assert response.status_code == 200
    assert [
        (category["name"], [item["name"] for item in category["subcategories"]])
        for category in response.json()
    ] == WORKBOOK_CATEGORIES
    assert [
        category["name"] for category in response.json() if category["is_bill_category"]
    ] == ["Bills"]


def test_members_have_default_labels(api: Api) -> None:
    response = api("GET", "/members")

    assert response.status_code == 200
    assert [member["name"] for member in response.json()] == ["Azul", "Pinketa"]


def test_member_label_can_be_changed(api: Api) -> None:
    azul_id = member_ids(api)["Azul"]

    response = api("PATCH", f"/members/{azul_id}", json={"name": "  Miguel  "})

    assert response.status_code == 200
    assert response.json() == {"id": azul_id, "name": "Miguel"}
    assert [member["name"] for member in api("GET", "/members").json()] == ["Miguel", "Pinketa"]
    summary = read_month(api, "/summary", "2025-11")
    assert [income["member_name"] for income in summary["incomes"]] == ["Miguel", "Pinketa"]


@pytest.mark.parametrize("name", ["", "   ", "x" * 51])
def test_member_label_rejects_invalid_names(api: Api, name: str) -> None:
    azul_id = member_ids(api)["Azul"]

    response = api("PATCH", f"/members/{azul_id}", json={"name": name})

    assert_invalid(response, "name")
    assert list(member_ids(api)) == ["Azul", "Pinketa"]


def test_unknown_member_cannot_be_renamed(api: Api) -> None:
    response = api("PATCH", "/members/9999", json={"name": "Nobody"})

    assert response.status_code == 404
    assert response.json() == {
        "detail": {"code": "not_found", "message": "Member does not exist."}
    }


def test_expense_is_recorded_with_category_and_subcategory(api: Api) -> None:
    response = record_expense(api, "2025-11-03", "12.36", "Beauty", "Hair")

    assert response.status_code == 201
    expense = response.json()
    assert expense["transaction_date"] == "2025-11-03"
    assert expense["amount"] == "12.36"
    assert expense["category"]["name"] == "Beauty"
    assert expense["subcategory"]["name"] == "Hair"
    assert read_month(api, "/expenses", "2025-11") == [expense]


@pytest.mark.parametrize("category", ["Groceries", "Clothes"])
def test_expense_without_subcategories_does_not_require_one(api: Api, category: str) -> None:
    response = record_expense(api, "2025-11-03", "30.33", category)

    assert response.status_code == 201
    assert response.json()["subcategory"] is None


@pytest.mark.parametrize("category", ["Beauty", "Transports", "Eat out"])
def test_expense_requires_subcategory_when_category_has_one(api: Api, category: str) -> None:
    response = record_expense(api, "2025-11-03", "30.33", category)

    assert_invalid(response, "subcategory_id")
    assert read_month(api, "/expenses", "2025-11") == []


def test_manual_expense_cannot_use_bills(api: Api) -> None:
    response = record_expense(api, "2025-11-03", "30.33", "Bills", "Water")

    assert_invalid(response, "category_id")
    assert read_month(api, "/summary", "2025-11")["total_expenses"] == "0.00"


def test_historical_bills_expense_is_hidden_but_included_in_totals(
    api: Api, ledger_app: FastAPI
) -> None:
    with Session(ledger_app.state.database_engine) as session:
        category = session.scalar(select(Category).where(Category.name == "Bills"))
        assert category is not None
        session.add(Expense(
            transaction_date=date(2025, 11, 3),
            amount=Decimal("30.33"),
            category_id=category.id,
        ))
        session.commit()

    assert record_expense(api, "2025-11-04", "12.00", "Groceries").status_code == 201
    expenses = read_month(api, "/expenses", "2025-11")
    assert len(expenses) == 1
    assert expenses[0]["category"]["name"] == "Groceries"
    summary = read_month(api, "/summary", "2025-11")
    assert summary["total_expenses"] == "42.33"
    assert summary["balance"] == "-42.33"
    bills_budget = next(
        item for item in summary["category_budgets"] if item["category"]["name"] == "Bills"
    )
    assert bills_budget["spent"] == "30.33"
    with Session(ledger_app.state.database_engine) as session:
        assert session.scalar(select(func.count(Expense.id))) == 2


def test_expense_dated_today_is_accepted(api: Api) -> None:
    response = record_expense(api, "2025-12-15", "5.00", "Groceries")

    assert response.status_code == 201


def test_expenses_count_towards_the_month_of_their_transaction_date(api: Api) -> None:
    for transaction_date, amount in [
        ("2024-02-29", "16.00"),
        ("2025-10-31", "1.00"),
        ("2025-11-01", "2.00"),
        ("2025-11-30", "4.00"),
        ("2025-12-01", "8.00"),
    ]:
        assert record_expense(api, transaction_date, amount, "Groceries").status_code == 201

    totals = {
        month: read_month(api, "/summary", month)["total_expenses"]
        for month in ["2024-02", "2024-03", "2025-10", "2025-11", "2025-12"]
    }
    assert totals == {
        "2024-02": "16.00",
        "2024-03": "0.00",
        "2025-10": "1.00",
        "2025-11": "6.00",
        "2025-12": "8.00",
    }
    november = read_month(api, "/expenses", "2025-11")
    assert [expense["transaction_date"] for expense in november] == ["2025-11-30", "2025-11-01"]


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"amount": "0"}, "amount"),
        ({"amount": "-5.00"}, "amount"),
        ({"amount": "12.345"}, "amount"),
        ({"amount": "abc"}, "amount"),
        ({"amount": "12345678901.00"}, "amount"),
        ({"transaction_date": "2025-12-16"}, "transaction_date"),
        ({"transaction_date": "2025-02-30"}, "transaction_date"),
        ({"category_id": 9999}, "category_id"),
        ({"category_id": 0}, "category_id"),
        ({"subcategory_id": 9999}, "subcategory_id"),
    ],
)
def test_invalid_expense_is_rejected_and_not_stored(api: Api, overrides: dict, field: str) -> None:
    payload = {
        "transaction_date": "2025-11-05",
        "amount": "10.00",
        **category_reference(api, "Beauty", "Hair"),
        **overrides,
    }

    response = api("POST", "/expenses", json=payload)

    assert_invalid(response, field)
    assert read_month(api, "/expenses", "2025-11") == []
    assert read_month(api, "/expenses", "2025-12") == []


def test_expense_requires_date_amount_and_category(api: Api) -> None:
    response = api("POST", "/expenses", json={})

    for field in ["transaction_date", "amount", "category_id"]:
        assert_invalid(response, field)


@pytest.mark.parametrize("category", ["Transports", "Groceries"])
def test_expense_rejects_subcategory_of_another_category(api: Api, category: str) -> None:
    payload = {
        "transaction_date": "2025-11-05",
        "amount": "10.00",
        "category_id": category_reference(api, category)["category_id"],
        "subcategory_id": category_reference(api, "Bills", "Water")["subcategory_id"],
    }

    response = api("POST", "/expenses", json=payload)

    assert_invalid(response, "subcategory_id")
    assert read_month(api, "/expenses", "2025-11") == []


def test_income_is_recorded_for_a_member_and_month(api: Api) -> None:
    response = record_income(api, "Azul", "2025-11", "4053.50")

    assert response.status_code == 201
    income = response.json()
    assert income["member_id"] == member_ids(api)["Azul"]
    assert income["month"] == "2025-11"
    assert income["amount"] == "4053.50"
    assert read_month(api, "/incomes", "2025-11") == [income]
    assert read_month(api, "/incomes", "2025-12") == []


def test_second_income_for_the_same_member_and_month_is_rejected(api: Api) -> None:
    assert record_income(api, "Azul", "2025-11", "4053.50").status_code == 201

    response = record_income(api, "Azul", "2025-11", "1.00")

    assert response.status_code == 409
    assert response.json() == {
        "detail": {
            "code": "conflict",
            "message": "Income for this member and month is already recorded.",
        }
    }
    assert [income["amount"] for income in read_month(api, "/incomes", "2025-11")] == ["4053.50"]
    assert record_income(api, "Pinketa", "2025-11", "2025.00").status_code == 201
    assert record_income(api, "Azul", "2025-12", "4053.50").status_code == 201


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"amount": "0"}, "amount"),
        ({"amount": "-1.00"}, "amount"),
        ({"amount": "10.001"}, "amount"),
        ({"month": "2025-13"}, "month"),
        ({"month": "2025-1"}, "month"),
        ({"month": "11-2025"}, "month"),
        ({"member_id": 9999}, "member_id"),
    ],
)
def test_invalid_income_is_rejected_and_not_stored(api: Api, overrides: dict, field: str) -> None:
    payload = {
        "member_id": member_ids(api)["Azul"],
        "month": "2025-11",
        "amount": "100.00",
        **overrides,
    }

    response = api("POST", "/incomes", json=payload)

    assert_invalid(response, field)
    assert read_month(api, "/incomes", "2025-11") == []


def test_summary_keeps_partner_incomes_separate_and_combines_totals(
    api: Api, ledger_app: FastAPI
) -> None:
    for expense in WORKBOOK_NOVEMBER_EXPENSES:
        if expense[2] == "Bills":
            reference = category_reference(api, expense[2], expense[3])
            with Session(ledger_app.state.database_engine) as session:
                session.add(Expense(
                    transaction_date=date.fromisoformat(expense[0]),
                    amount=Decimal(expense[1]),
                    **reference,
                ))
                session.commit()
        else:
            assert record_expense(api, *expense).status_code == 201
    assert record_income(api, "Azul", "2025-11", "4053.50").status_code == 201
    assert record_income(api, "Pinketa", "2025-11", "2025.00").status_code == 201
    members = member_ids(api)

    assert read_month(api, "/summary", "2025-11") == {
        "month": "2025-11",
        "incomes": [
            {"member_id": members["Azul"], "member_name": "Azul", "amount": "4053.50"},
            {"member_id": members["Pinketa"], "member_name": "Pinketa", "amount": "2025.00"},
        ],
        "total_income": "6078.50",
        "total_expenses": "707.23",
        "balance": "5371.27",
        "category_budgets": [
            {"category": {"id": 1, "name": "Bills"}, "month": "2025-11", "limit": None, "spent": "30.33", "percent": "0.00", "state": "unset"},
            {"category": {"id": 2, "name": "Groceries"}, "month": "2025-11", "limit": None, "spent": "52.89", "percent": "0.00", "state": "unset"},
            {"category": {"id": 3, "name": "Beauty"}, "month": "2025-11", "limit": None, "spent": "2.99", "percent": "0.00", "state": "unset"},
            {"category": {"id": 4, "name": "Transports"}, "month": "2025-11", "limit": None, "spent": "18.89", "percent": "0.00", "state": "unset"},
            {"category": {"id": 5, "name": "Eat out"}, "month": "2025-11", "limit": None, "spent": "81.19", "percent": "0.00", "state": "unset"},
            {"category": {"id": 6, "name": "Clothes"}, "month": "2025-11", "limit": None, "spent": "520.94", "percent": "0.00", "state": "unset"},
        ],
    }


def test_summary_of_a_month_without_records_is_zero(api: Api) -> None:
    summary = read_month(api, "/summary", "2025-11")

    assert [income["amount"] for income in summary["incomes"]] == [None, None]
    assert summary["total_income"] == "0.00"
    assert summary["total_expenses"] == "0.00"
    assert summary["balance"] == "0.00"


def test_summary_uses_exact_decimal_arithmetic(api: Api) -> None:
    assert record_expense(api, "2025-11-01", "0.10", "Groceries").status_code == 201
    assert record_expense(api, "2025-11-02", "0.20", "Groceries").status_code == 201
    assert record_income(api, "Azul", "2025-11", "0.30").status_code == 201

    summary = read_month(api, "/summary", "2025-11")

    assert summary["total_expenses"] == "0.30"
    assert summary["balance"] == "0.00"


def test_summary_balance_is_negative_when_expenses_exceed_income(api: Api) -> None:
    assert record_expense(api, "2025-11-01", "150.25", "Clothes").status_code == 201
    assert record_income(api, "Pinketa", "2025-11", "100.00").status_code == 201

    assert read_month(api, "/summary", "2025-11")["balance"] == "-50.25"


@pytest.mark.parametrize("path", ["/expenses", "/incomes", "/summary"])
@pytest.mark.parametrize("params", [{"month": "2025-13"}, {"month": "november"}, {}])
def test_month_query_must_be_a_valid_month(api: Api, path: str, params: dict) -> None:
    response = api("GET", path, params=params)

    assert_invalid(response, "month")


def test_failed_expense_write_is_reported_and_not_stored(api: Api, ledger_app: FastAPI) -> None:
    with failing_commits(ledger_app):
        response = record_expense(api, "2025-11-03", "12.36", "Beauty", "Hair")

    assert_sanitized_storage_failure(response)
    assert read_month(api, "/expenses", "2025-11") == []
    assert read_month(api, "/summary", "2025-11")["total_expenses"] == "0.00"


def test_failed_income_write_is_reported_and_not_stored(api: Api, ledger_app: FastAPI) -> None:
    with failing_commits(ledger_app):
        response = record_income(api, "Azul", "2025-11", "4053.50")

    assert_sanitized_storage_failure(response)
    assert read_month(api, "/incomes", "2025-11") == []
    assert record_income(api, "Azul", "2025-11", "4053.50").status_code == 201


def test_failed_member_rename_is_reported_and_not_stored(api: Api, ledger_app: FastAPI) -> None:
    azul_id = member_ids(api)["Azul"]

    with failing_commits(ledger_app):
        response = api("PATCH", f"/members/{azul_id}", json={"name": "Miguel"})

    assert_sanitized_storage_failure(response)
    assert list(member_ids(api)) == ["Azul", "Pinketa"]


@pytest.mark.parametrize(
    "path",
    ["/categories", "/members", "/expenses?month=2025-11", "/incomes?month=2025-11", "/summary?month=2025-11"],
)
def test_reads_report_an_unavailable_database_without_details(path: str) -> None:
    engine = MagicMock(spec=Engine)
    engine.connect.side_effect = SQLAlchemyError("private connection detail")
    app = create_app(settings=Settings(_env_file=None), engine=engine)

    response = send(app, "GET", path)

    assert_sanitized_storage_failure(response)


def set_budget(api: Api, category: str, month: str, amount: str) -> Response:
    category_id = category_reference(api, category)["category_id"]
    return api("PUT", f"/budgets/{category_id}", params={"month": month}, json={"amount": amount})


def test_budget_write_allows_cross_origin_put(ledger_app: FastAPI) -> None:
    response = send(
        ledger_app,
        "OPTIONS",
        "/budgets/1?month=2025-11",
        headers={
            "Origin": "http://localhost:4200",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert "PUT" in response.headers["access-control-allow-methods"]


@pytest.mark.parametrize(
    ("spent", "expected_state", "expected_percent"),
    [
        ("79.99", "under", "79.99"),
        ("80.00", "warning", "80.00"),
        ("100.00", "warning", "100.00"),
        ("100.01", "exceeded", "100.01"),
    ],
)
def test_category_budget_boundaries(
    api: Api, spent: str, expected_state: str, expected_percent: str
) -> None:
    assert set_budget(api, "Groceries", "2025-11", "100.00").status_code == 200
    assert record_expense(api, "2025-11-05", spent, "Groceries").status_code == 201

    budget = next(
        item
        for item in read_month(api, "/summary", "2025-11")["category_budgets"]
        if item["category"]["name"] == "Groceries"
    )

    assert budget["limit"] == "100.00"
    assert budget["spent"] == spent
    assert budget["percent"] == expected_percent
    assert budget["state"] == expected_state


def test_budget_does_not_warn_below_exact_threshold_when_display_rounds_to_80(
    api: Api,
) -> None:
    assert set_budget(api, "Groceries", "2025-11", "200.01").status_code == 200
    assert record_expense(api, "2025-11-05", "160.00", "Groceries").status_code == 201

    budget = next(
        item
        for item in read_month(api, "/summary", "2025-11")["category_budgets"]
        if item["category"]["name"] == "Groceries"
    )

    assert budget["percent"] == "80.00"
    assert budget["state"] == "under"


def test_budget_can_be_viewed_and_updated_for_each_month(api: Api) -> None:
    assert set_budget(api, "Bills", "2025-11", "250.00").status_code == 200
    assert set_budget(api, "Bills", "2025-11", "300.00").status_code == 200
    assert set_budget(api, "Bills", "2025-12", "400.00").status_code == 200

    november = next(
        item
        for item in read_month(api, "/summary", "2025-11")["category_budgets"]
        if item["category"]["name"] == "Bills"
    )
    december = next(
        item
        for item in read_month(api, "/summary", "2025-12")["category_budgets"]
        if item["category"]["name"] == "Bills"
    )

    assert november["limit"] == "300.00"
    assert november["month"] == "2025-11"
    assert december["limit"] == "400.00"
    assert december["month"] == "2025-12"


@pytest.mark.parametrize(
    ("category_id", "month", "amount", "field"),
    [
        (9999, "2025-11", "100.00", "category_id"),
        (1, "2025-13", "100.00", "month"),
        (1, "2025-11", "0", "amount"),
        (1, "2025-11", "-1.00", "amount"),
        (1, "2025-11", "12.345", "amount"),
    ],
)
def test_invalid_budget_is_rejected(
    api: Api, category_id: int, month: str, amount: str, field: str
) -> None:
    response = api(
        "PUT",
        f"/budgets/{category_id}",
        params={"month": month},
        json={"amount": amount},
    )

    assert_invalid(response, field)


def test_failed_budget_write_is_reported_and_not_stored(
    api: Api, ledger_app: FastAPI
) -> None:
    category_id = category_reference(api, "Bills")["category_id"]

    with failing_commits(ledger_app):
        response = api(
            "PUT",
            f"/budgets/{category_id}",
            params={"month": "2025-11"},
            json={"amount": "250.00"},
        )

    assert_sanitized_storage_failure(response)
    bills = next(
        item
        for item in read_month(api, "/summary", "2025-11")["category_budgets"]
        if item["category"]["name"] == "Bills"
    )
    assert bills["limit"] is None


def test_one_off_bill_stays_unpaid_and_is_paid_once(api: Api) -> None:
    category = category_reference(api, "Bills", "Water")
    created = api(
        "POST",
        "/bills",
        json={
            "recurrence": "one_off",
            "due_date": "2025-12-20",
            "amount": "45.00",
            **category,
        },
    )
    assert created.status_code == 201
    assert read_month(api, "/summary", "2025-12")["total_expenses"] == "0.00"

    pending = next(
        item for item in read_month(api, "/bills", "2025-12")
        if item["due_date"] == "2025-12-20"
    )
    assert pending["status"] == "pending"
    assert pending["amount"] == "45.00"

    adjusted = api(
        "PUT",
        f"/bills/occurrences/{pending['id']}/amount",
        json={"amount": "43.25"},
    )
    assert adjusted.status_code == 200
    assert adjusted.json()["amount"] == "43.25"

    paid = api(
        "POST",
        f"/bills/occurrences/{pending['id']}/pay",
        json={"paid_amount": "43.25", "paid_date": "2025-12-14"},
    )
    assert paid.status_code == 200
    assert paid.json()["status"] == "paid"
    assert paid.json()["paid_amount"] == "43.25"
    assert paid.json()["paid_date"] == "2025-12-14"
    assert read_month(api, "/summary", "2025-12")["total_expenses"] == "43.25"
    assert read_month(api, "/expenses", "2025-12") == []

    repeated = api(
        "POST",
        f"/bills/occurrences/{pending['id']}/pay",
        json={"paid_amount": "43.25", "paid_date": "2025-12-14"},
    )
    assert repeated.status_code == 409
    assert read_month(api, "/summary", "2025-12")["total_expenses"] == "43.25"


def test_monthly_bill_generates_occurrences_and_adjusted_amount(api: Api) -> None:
    category = category_reference(api, "Bills", "Home Internet")
    created = api(
        "POST",
        "/bills",
        json={
            "recurrence": "monthly",
            "due_date": "2025-10-31",
            "amount": "40.00",
            **category,
        },
    )
    assert created.status_code == 201

    november = read_month(api, "/bills", "2025-11")
    assert any(
        item["due_date"] == "2025-11-30"
        and item["amount"] == "40.00"
        for item in november
    )
    assert any(item["due_date"] == "2025-10-31" for item in november)

    december = read_month(api, "/bills", "2025-12")
    assert any(item["due_date"] == "2025-12-31" for item in december)


def test_overdue_bill_and_invalid_payment_are_reported(api: Api) -> None:
    category = category_reference(api, "Bills", "Heating")
    created = api(
        "POST",
        "/bills",
        json={
            "recurrence": "one_off",
            "due_date": "2025-12-10",
            "amount": "80.00",
            **category,
        },
    )
    occurrence = next(
        item for item in read_month(api, "/bills", "2025-12")
        if item["id"] >= 1
    )
    assert created.status_code == 201
    assert occurrence["status"] == "overdue"

    future = api(
        "POST",
        f"/bills/occurrences/{occurrence['id']}/pay",
        json={"paid_amount": "80.00", "paid_date": "2025-12-16"},
    )
    assert_invalid(future, "paid_date")
    assert read_month(api, "/summary", "2025-12")["total_expenses"] == "0.00"


def test_bill_payment_counts_in_paid_month_and_budget(api: Api) -> None:
    category = category_reference(api, "Bills", "Water")
    assert set_budget(api, "Bills", "2025-11", "100.00").status_code == 200
    assert set_budget(api, "Bills", "2025-12", "100.00").status_code == 200
    assert api("POST", "/bills", json={
        "recurrence": "monthly", "due_date": "2025-11-30",
        "amount": "40.00", **category,
    }).status_code == 201
    occurrence = next(
        bill for bill in read_month(api, "/bills", "2025-11")
        if bill["due_date"] == "2025-11-30"
    )
    for month in ("2025-11", "2025-12"):
        summary = read_month(api, "/summary", month)
        assert summary["total_expenses"] == "0.00"
        assert summary["category_budgets"][0]["spent"] == "0.00"
    assert api("PUT", f"/bills/occurrences/{occurrence['id']}/amount",
               json={"amount": "80.00"}).status_code == 200
    assert api("POST", f"/bills/occurrences/{occurrence['id']}/pay",
               json={"paid_amount": "80.00", "paid_date": "2025-12-01"}).status_code == 200
    november = read_month(api, "/summary", "2025-11")
    december = read_month(api, "/summary", "2025-12")
    assert november["total_expenses"] == "0.00"
    assert november["category_budgets"][0]["spent"] == "0.00"
    assert december["total_expenses"] == "80.00"
    assert december["category_budgets"][0]["spent"] == "80.00"
    assert december["category_budgets"][0]["state"] == "warning"
    assert december["balance"] == "-80.00"
    assert read_month(api, "/expenses", "2025-12") == []
    next_occurrence = next(
        bill for bill in read_month(api, "/bills", "2025-12")
        if bill["due_date"] == "2025-12-30"
    )
    assert next_occurrence["amount"] == "40.00"
    assert next_occurrence["status"] == "pending"


def test_failed_bill_payment_rolls_back_expense(api: Api, ledger_app: FastAPI) -> None:
    assert api("POST", "/bills", json={
        "recurrence": "one_off", "due_date": "2025-12-10",
        "amount": "40.00", **category_reference(api, "Bills", "Water"),
    }).status_code == 201
    occurrence = read_month(api, "/bills", "2025-12")[0]
    with failing_commits(ledger_app):
        response = api("POST", f"/bills/occurrences/{occurrence['id']}/pay",
                       json={"paid_amount": "40.00", "paid_date": "2025-12-10"})
    assert_sanitized_storage_failure(response)
    assert read_month(api, "/expenses", "2025-12") == []
    assert read_month(api, "/bills", "2025-12")[0]["status"] == "overdue"
    assert api("POST", f"/bills/occurrences/{occurrence['id']}/pay",
               json={"paid_amount": "40.00", "paid_date": "2025-12-10"}).status_code == 200


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"recurrence": "weekly"}, "recurrence"),
        ({"amount": "0"}, "amount"),
        ({"due_date": "2025-02-30"}, "due_date"),
        ({"category_id": 9999}, "category_id"),
        ({"subcategory_id": 9999}, "subcategory_id"),
    ],
)
def test_invalid_bill_is_rejected(api: Api, overrides: dict, field: str) -> None:
    response = api("POST", "/bills", json={
        "recurrence": "monthly", "due_date": "2025-12-10", "amount": "40.00",
        **category_reference(api, "Bills", "Water"), **overrides,
    })
    assert_invalid(response, field)
    assert read_month(api, "/bills", "2025-12") == []


@pytest.mark.parametrize(
    ("category", "subcategory", "field"),
    [
        ("Bills", None, "subcategory_id"),
        ("Groceries", None, "category_id"),
        ("Beauty", "Hair", "category_id"),
    ],
)
def test_bill_requires_bills_subcategory(
    api: Api, category: str, subcategory: str | None, field: str
) -> None:
    reference = category_reference(api, category, subcategory)
    if category != "Bills" and subcategory is None:
        reference["subcategory_id"] = category_reference(api, "Bills", "Water")["subcategory_id"]
    response = api("POST", "/bills", json={
        "recurrence": "one_off", "due_date": "2025-12-10", "amount": "40.00",
        **reference,
    })
    assert_invalid(response, field)
    assert read_month(api, "/bills", "2025-12") == []
    assert read_month(api, "/summary", "2025-12")["total_expenses"] == "0.00"


def test_bill_requires_subcategory_field(api: Api) -> None:
    response = api("POST", "/bills", json={
        "recurrence": "one_off", "due_date": "2025-12-10", "amount": "40.00",
        "category_id": category_reference(api, "Bills")["category_id"],
    })
    assert_invalid(response, "subcategory_id")
    assert read_month(api, "/bills", "2025-12") == []


def test_bill_rejects_subcategory_from_another_category(api: Api) -> None:
    response = api("POST", "/bills", json={
        "recurrence": "one_off", "due_date": "2025-12-10", "amount": "40.00",
        "category_id": category_reference(api, "Bills")["category_id"],
        "subcategory_id": category_reference(api, "Beauty", "Hair")["subcategory_id"],
    })
    assert_invalid(response, "subcategory_id")
    assert read_month(api, "/bills", "2025-12") == []


@pytest.mark.parametrize("subcategory", ["Water", "Electricity", "Heating", "Home Internet", "Phone Plan"])
def test_bill_accepts_each_approved_subcategory(api: Api, subcategory: str) -> None:
    response = api("POST", "/bills", json={
        "recurrence": "one_off", "due_date": "2025-12-10", "amount": "40.00",
        **category_reference(api, "Bills", subcategory),
    })
    assert response.status_code == 201
    assert response.json()["subcategory"]["name"] == subcategory


def test_bill_accepts_new_stored_subcategory(api: Api, ledger_app: FastAPI) -> None:
    with Session(ledger_app.state.database_engine) as session:
        category = session.scalar(select(Category).where(Category.name == "Bills"))
        assert category is not None
        subcategory = Subcategory(category_id=category.id, name="Other", position=99)
        session.add(subcategory)
        session.commit()
        category_id, subcategory_id = category.id, subcategory.id

    response = api("POST", "/bills", json={
        "recurrence": "one_off", "due_date": "2025-12-10", "amount": "40.00",
        "category_id": category_id, "subcategory_id": subcategory_id,
    })
    assert response.status_code == 201
    assert response.json()["subcategory"]["name"] == "Other"


def test_bill_classification_does_not_depend_on_category_name(
    api: Api, ledger_app: FastAPI
) -> None:
    with Session(ledger_app.state.database_engine) as session:
        bill_category = session.scalar(select(Category).where(Category.name == "Bills"))
        other_category = session.scalar(select(Category).where(Category.name == "Groceries"))
        assert bill_category is not None and other_category is not None
        bill_category.name = "Utilities"
        session.flush()
        other_category.name = "Bills"
        session.add(Expense(
            transaction_date=date(2025, 11, 3),
            amount=Decimal("10.00"),
            category_id=bill_category.id,
        ))
        session.commit()

    categories = {item["name"]: item for item in api("GET", "/categories").json()}
    assert categories["Utilities"]["is_bill_category"] is True
    assert categories["Bills"]["is_bill_category"] is False
    assert_invalid(record_expense(api, "2025-11-03", "5.00", "Utilities", "Water"), "category_id")
    assert record_expense(api, "2025-11-03", "7.00", "Bills").status_code == 201
    expenses = read_month(api, "/expenses", "2025-11")
    assert [expense["category"]["name"] for expense in expenses] == ["Bills"]
    assert read_month(api, "/summary", "2025-11")["total_expenses"] == "17.00"
    response = api("POST", "/bills", json={
        "recurrence": "one_off", "due_date": "2025-12-10", "amount": "40.00",
        **category_reference(api, "Utilities", "Water"),
    })
    assert response.status_code == 201
    response = api("POST", "/bills", json={
        "recurrence": "one_off", "due_date": "2025-12-10", "amount": "40.00",
        "category_id": categories["Bills"]["id"],
        "subcategory_id": category_reference(api, "Utilities", "Water")["subcategory_id"],
    })
    assert_invalid(response, "category_id")


def test_paid_bill_cannot_be_adjusted(api: Api) -> None:
    assert api("POST", "/bills", json={
        "recurrence": "one_off", "due_date": "2025-12-10",
        "amount": "40.00", **category_reference(api, "Bills", "Water"),
    }).status_code == 201
    occurrence = read_month(api, "/bills", "2025-12")[0]
    assert api("POST", f"/bills/occurrences/{occurrence['id']}/pay",
               json={"paid_amount": "40.00", "paid_date": "2025-12-10"}).status_code == 200
    response = api("PUT", f"/bills/occurrences/{occurrence['id']}/amount",
                   json={"amount": "20.00"})
    assert response.status_code == 409
    assert read_month(api, "/expenses", "2025-12") == []
    assert read_month(api, "/summary", "2025-12")["total_expenses"] == "40.00"


def test_concurrent_bill_payments_create_one_expense(api: Api, ledger_app: FastAPI) -> None:
    if ledger_app.state.database_engine.dialect.name != "postgresql":
        pytest.skip("Concurrent transaction test requires PostgreSQL.")
    assert api("POST", "/bills", json={
        "recurrence": "one_off", "due_date": "2025-12-10",
        "amount": "40.00", **category_reference(api, "Bills", "Water"),
    }).status_code == 201
    occurrence = read_month(api, "/bills", "2025-12")[0]
    barrier = Barrier(2, timeout=10)
    start = Barrier(2, timeout=10)

    def synchronize_unlocked_reads(conn, cursor, statement, parameters, context, executemany):
        sql = statement.lower()
        if sql.startswith("select") and "from bill_occurrences" in sql and "for update" not in sql:
            barrier.wait()

    engine = ledger_app.state.database_engine
    event.listen(engine, "after_cursor_execute", synchronize_unlocked_reads)
    try:
        def pay():
            start.wait()
            return api("POST", f"/bills/occurrences/{occurrence['id']}/pay",
                       json={"paid_amount": "40.00", "paid_date": "2025-12-10"})
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: pay(), range(2)))
    finally:
        event.remove(engine, "after_cursor_execute", synchronize_unlocked_reads)
    assert sorted(response.status_code for response in responses) == [200, 409]
    assert read_month(api, "/expenses", "2025-12") == []
    with Session(engine) as session:
        assert session.scalar(select(func.count(Expense.id))) == 1


def test_concurrent_bill_listing_generates_one_occurrence(api: Api, ledger_app: FastAPI) -> None:
    if ledger_app.state.database_engine.dialect.name != "postgresql":
        pytest.skip("Concurrent transaction test requires PostgreSQL.")
    assert api("POST", "/bills", json={
        "recurrence": "monthly", "due_date": "2025-11-30",
        "amount": "40.00", **category_reference(api, "Bills", "Water"),
    }).status_code == 201
    start = Barrier(2, timeout=10)
    unlocked_reads = Barrier(2, timeout=10)

    def synchronize_unlocked_generation(conn, cursor, statement, parameters, context, executemany):
        sql = statement.lower()
        if sql.startswith("select") and "from bills " in sql:
            conn.info["bill_generation_locked"] = "for update" in sql
        if (
            sql.startswith("select bill_occurrences.id")
            and isinstance(parameters, dict)
            and date(2025, 12, 30) in parameters.values()
            and not conn.info.get("bill_generation_locked", False)
        ):
            unlocked_reads.wait()

    def list_bills():
        start.wait()
        return api("GET", "/bills", params={"month": "2025-12"})

    engine = ledger_app.state.database_engine
    event.listen(engine, "after_cursor_execute", synchronize_unlocked_generation)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: list_bills(), range(2)))
    finally:
        event.remove(engine, "after_cursor_execute", synchronize_unlocked_generation)
    assert [response.status_code for response in responses] == [200, 200]
    for response in responses:
        december = [bill for bill in response.json() if bill["due_date"] == "2025-12-30"]
        assert len(december) == 1
        assert december[0]["amount"] == "40.00"
    assert responses[0].json() == responses[1].json()
