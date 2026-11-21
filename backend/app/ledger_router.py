from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app import ledger_service
from app.database import get_session
from app.months import Month
from app.schemas import (
    MAX_ENTITY_ID,
    CategoryRead,
    ExpenseCreate,
    ExpenseRead,
    IncomeCreate,
    IncomeRead,
    MemberRead,
    MemberRename,
    MonthlySummary,
)

router = APIRouter(tags=["ledger"])


def get_today() -> date:
    return date.today()


SessionDependency = Annotated[Session, Depends(get_session)]
MonthQuery = Annotated[Month, Query(description="Calendar month in YYYY-MM format.")]


@router.get("/categories", response_model=list[CategoryRead])
def read_categories(session: SessionDependency):
    return ledger_service.list_categories(session)


@router.get("/members", response_model=list[MemberRead])
def read_members(session: SessionDependency):
    return ledger_service.list_members(session)


@router.patch("/members/{member_id}", response_model=MemberRead)
def rename_member(
    member_id: Annotated[int, Path(ge=1, le=MAX_ENTITY_ID)],
    change: MemberRename,
    session: SessionDependency,
):
    return ledger_service.rename_member(session, member_id, change.name)


@router.post("/expenses", response_model=ExpenseRead, status_code=201)
def create_expense(
    entry: ExpenseCreate,
    session: SessionDependency,
    today: Annotated[date, Depends(get_today)],
):
    return ledger_service.record_expense(session, entry, today)


@router.get("/expenses", response_model=list[ExpenseRead])
def read_expenses(month: MonthQuery, session: SessionDependency):
    return ledger_service.list_expenses(session, month)


@router.post("/incomes", response_model=IncomeRead, status_code=201)
def create_income(entry: IncomeCreate, session: SessionDependency):
    return ledger_service.record_income(session, entry)


@router.get("/incomes", response_model=list[IncomeRead])
def read_incomes(month: MonthQuery, session: SessionDependency):
    return ledger_service.list_incomes(session, month)


@router.get("/summary", response_model=MonthlySummary)
def read_summary(month: MonthQuery, session: SessionDependency):
    return ledger_service.get_monthly_summary(session, month)
