from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from sqlalchemy import ColumnElement, and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.database import commit
from app.errors import ConflictError, InvalidEntryError, NotFoundError
from app.models import (
    Category,
    CategoryBudget,
    Expense,
    Income,
    Member,
    Subcategory,
)
from app.months import month_bounds
from app.schemas import (
    CategoryBudgetRead,
    ExpenseCreate,
    IncomeCreate,
    MemberIncome,
    MonthlySummary,
)

ZERO = Decimal("0.00")


def list_categories(session: Session) -> Sequence[Category]:
    statement = (
        select(Category)
        .options(selectinload(Category.subcategories))
        .order_by(Category.position)
    )
    return session.scalars(statement).all()


def list_members(session: Session) -> Sequence[Member]:
    return session.scalars(select(Member).order_by(Member.id)).all()


def rename_member(session: Session, member_id: int, name: str) -> Member:
    member = session.get(Member, member_id)
    if member is None:
        raise NotFoundError("Member does not exist.")
    member.name = name
    commit(session)
    return member


def record_expense(session: Session, entry: ExpenseCreate, today: date) -> Expense:
    if entry.transaction_date > today:
        raise InvalidEntryError(
            "Transaction date cannot be in the future.",
            field="transaction_date",
        )
    category = session.get(Category, entry.category_id)
    if category is None:
        raise InvalidEntryError("Category does not exist.", field="category_id")
    subcategory = None
    if entry.subcategory_id is not None:
        subcategory = session.get(Subcategory, entry.subcategory_id)
        if subcategory is None or subcategory.category_id != category.id:
            raise InvalidEntryError(
                "Subcategory does not belong to the category.",
                field="subcategory_id",
            )

    expense = Expense(
        transaction_date=entry.transaction_date,
        amount=entry.amount,
        category=category,
        subcategory=subcategory,
    )
    session.add(expense)
    commit(session)
    return expense


def list_expenses(session: Session, month: date) -> Sequence[Expense]:
    statement = (
        select(Expense)
        .options(joinedload(Expense.category), joinedload(Expense.subcategory))
        .where(_in_month(month))
        .order_by(Expense.transaction_date.desc(), Expense.id.desc())
    )
    return session.scalars(statement).all()


def record_income(session: Session, entry: IncomeCreate) -> Income:
    if session.get(Member, entry.member_id) is None:
        raise InvalidEntryError("Member does not exist.", field="member_id")

    income = Income(member_id=entry.member_id, month=entry.month, amount=entry.amount)
    session.add(income)
    try:
        commit(session)
    except IntegrityError as error:
        raise ConflictError(
            "Income for this member and month is already recorded."
        ) from error
    return income


def list_incomes(session: Session, month: date) -> Sequence[Income]:
    statement = select(Income).where(Income.month == month).order_by(Income.member_id)
    return session.scalars(statement).all()


def get_monthly_summary(session: Session, month: date) -> MonthlySummary:
    income_rows = session.execute(
        select(Member, Income.amount)
        .outerjoin(Income, and_(Income.member_id == Member.id, Income.month == month))
        .order_by(Member.id)
    ).all()
    incomes = [
        MemberIncome(member_id=member.id, member_name=member.name, amount=amount)
        for member, amount in income_rows
    ]
    total_income = sum(
        (income.amount for income in incomes if income.amount is not None),
        ZERO,
    )
    total_expenses = (
        session.scalar(select(func.sum(Expense.amount)).where(_in_month(month))) or ZERO
    )
    category_budgets = list_category_budgets(session, month)
    return MonthlySummary(
        month=month,
        incomes=incomes,
        total_income=total_income,
        total_expenses=total_expenses,
        balance=total_income - total_expenses,
        category_budgets=category_budgets,
    )


def set_category_budget(
    session: Session, category_id: int, month: date, amount: Decimal
) -> CategoryBudgetRead:
    category = session.get(Category, category_id)
    if category is None:
        raise InvalidEntryError("Category does not exist.", field="category_id")

    budget = session.scalar(
        select(CategoryBudget).where(
            CategoryBudget.category_id == category_id,
            CategoryBudget.month == month,
        )
    )
    if budget is None:
        budget = CategoryBudget(category_id=category_id, month=month, amount=amount)
        session.add(budget)
    else:
        budget.amount = amount
    commit(session)

    return next(
        item
        for item in list_category_budgets(session, month)
        if item.category.id == category_id
    )


def list_category_budgets(session: Session, month: date) -> list[CategoryBudgetRead]:
    categories = list_categories(session)
    budgets = {
        budget.category_id: budget.amount
        for budget in session.scalars(
            select(CategoryBudget).where(CategoryBudget.month == month)
        ).all()
    }
    spent_rows = session.execute(
        select(Expense.category_id, func.sum(Expense.amount))
        .where(_in_month(month))
        .group_by(Expense.category_id)
    ).all()
    spent = {category_id: amount for category_id, amount in spent_rows}

    result: list[CategoryBudgetRead] = []
    for category in categories:
        limit = budgets.get(category.id)
        actual = spent.get(category.id, ZERO)
        if limit is None:
            percent = ZERO
            state = "unset"
        else:
            percent = (actual * Decimal("100") / limit).quantize(Decimal("0.01"))
            state = (
                "exceeded"
                if actual > limit
                else "warning"
                if actual * Decimal("100") >= limit * Decimal("80")
                else "under"
            )
        result.append(
            CategoryBudgetRead(
                category={"id": category.id, "name": category.name},
                month=month,
                limit=limit,
                spent=actual,
                percent=percent,
                state=state,
            )
        )
    return result


def _in_month(month: date) -> ColumnElement[bool]:
    first_day, last_day = month_bounds(month)
    return Expense.transaction_date.between(first_day, last_day)
