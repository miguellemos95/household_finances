from collections.abc import Sequence
import calendar
from datetime import date
from decimal import Decimal

from sqlalchemy import ColumnElement, and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.database import commit
from app.errors import ConflictError, InvalidEntryError, NotFoundError
from app.models import (
    Bill,
    BillOccurrence,
    Category,
    CategoryBudget,
    Expense,
    Income,
    Member,
    Subcategory,
)
from app.months import month_bounds
from app.schemas import (
    BillCreate,
    BillOccurrenceRead,
    BillRead,
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


def _validate_subcategory(
    session: Session, category: Category, subcategory_id: int | None
) -> Subcategory | None:
    if subcategory_id is None:
        if category.subcategories:
            raise InvalidEntryError("Subcategory is required.", field="subcategory_id")
        return None
    subcategory = session.get(Subcategory, subcategory_id)
    if subcategory is None or subcategory.category_id != category.id:
        raise InvalidEntryError(
            "Subcategory does not belong to the category.",
            field="subcategory_id",
        )
    return subcategory


def record_expense(session: Session, entry: ExpenseCreate, today: date) -> Expense:
    if entry.transaction_date > today:
        raise InvalidEntryError(
            "Transaction date cannot be in the future.",
            field="transaction_date",
        )
    category = session.get(Category, entry.category_id)
    if category is None:
        raise InvalidEntryError("Category does not exist.", field="category_id")
    if category.is_bill_category:
        raise InvalidEntryError("Bills cannot be recorded as manual expenses.", field="category_id")
    subcategory = _validate_subcategory(session, category, entry.subcategory_id)

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
        .join(Expense.category)
        .options(joinedload(Expense.category), joinedload(Expense.subcategory))
        .where(_in_month(month), Category.is_bill_category.is_(False))
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


def create_bill(
    session: Session, entry: BillCreate, today: date
) -> Bill:
    if entry.recurrence not in {"one_off", "monthly"}:
        raise InvalidEntryError(
            "Recurrence must be one_off or monthly.",
            field="recurrence",
        )
    category = session.get(Category, entry.category_id)
    if category is None:
        raise InvalidEntryError("Category does not exist.", field="category_id")
    if not category.is_bill_category:
        raise InvalidEntryError("Choose the bill category.", field="category_id")
    subcategory = _validate_subcategory(session, category, entry.subcategory_id)
    if subcategory is None:
        raise InvalidEntryError("Choose a valid bill subcategory.", field="subcategory_id")

    due_day = entry.due_date.day if entry.recurrence == "monthly" else None
    bill = Bill(
        recurrence=entry.recurrence,
        first_due_date=entry.due_date,
        due_day=due_day,
        default_amount=entry.amount,
        category=category,
        subcategory=subcategory,
    )
    first_occurrence = BillOccurrence(
        due_date=entry.due_date,
        amount=entry.amount,
        status="pending",
    )
    bill.occurrences.append(first_occurrence)
    session.add(bill)
    commit(session)
    return bill


def list_bill_occurrences(
    session: Session, month: date, today: date
) -> list[BillOccurrenceRead]:
    bills = session.scalars(
        select(Bill)
        .options(joinedload(Bill.category), joinedload(Bill.subcategory))
        .order_by(Bill.id)
        .with_for_update(of=Bill)
    ).all()
    for bill in bills:
        if bill.recurrence == "monthly":
            cursor = bill.first_due_date.replace(day=1)
            while cursor <= month.replace(day=1):
                due_date = _due_date_for_month(cursor.year, cursor.month, bill.due_day)
                if not session.scalar(
                    select(BillOccurrence.id).where(
                        BillOccurrence.bill_id == bill.id,
                        BillOccurrence.due_date == due_date,
                    )
                ):
                    session.add(
                        BillOccurrence(
                            bill=bill,
                            due_date=due_date,
                            amount=bill.default_amount,
                            status="pending",
                        )
                    )
                if cursor == month.replace(day=1):
                    break
                cursor = _next_month(cursor)
    commit(session)

    first_day, last_day = month_bounds(month)
    occurrences = session.scalars(
        select(BillOccurrence)
        .options(
            joinedload(BillOccurrence.bill).joinedload(Bill.category),
            joinedload(BillOccurrence.bill).joinedload(Bill.subcategory),
        )
        .join(Bill, BillOccurrence.bill_id == Bill.id)
        .where(
            (BillOccurrence.due_date.between(first_day, last_day))
            | (
                (BillOccurrence.status != "paid")
                & (BillOccurrence.due_date < first_day)
            )
            | (
                (BillOccurrence.status == "paid")
                & (BillOccurrence.paid_date.between(first_day, last_day))
            )
        )
        .order_by(BillOccurrence.due_date, BillOccurrence.id)
    ).all()

    return [_bill_occurrence_read(occurrence, today) for occurrence in occurrences]


def _bill_occurrence_read(occurrence: BillOccurrence, today: date) -> BillOccurrenceRead:
    result = BillOccurrenceRead.model_validate(occurrence)
    if result.status != "paid":
        result.status = "overdue" if result.due_date < today else "pending"
    return result


def adjust_bill_occurrence(
    session: Session, occurrence_id: int, amount: Decimal, today: date
) -> BillOccurrenceRead:
    occurrence = session.scalar(
        select(BillOccurrence)
        .options(joinedload(BillOccurrence.bill).joinedload(Bill.category),
                 joinedload(BillOccurrence.bill).joinedload(Bill.subcategory))
        .where(BillOccurrence.id == occurrence_id)
        .with_for_update(of=BillOccurrence)
    )
    if occurrence is None:
        raise NotFoundError("Bill occurrence does not exist.")
    if occurrence.status == "paid":
        raise ConflictError("A paid bill occurrence cannot be adjusted.")
    occurrence.amount = amount
    commit(session)
    return _bill_occurrence_read(occurrence, today)


def pay_bill_occurrence(
    session: Session,
    occurrence_id: int,
    paid_amount: Decimal,
    paid_date: date,
    today: date,
) -> BillOccurrenceRead:
    if paid_date > today:
        raise InvalidEntryError(
            "Paid date cannot be in the future.",
            field="paid_date",
        )
    occurrence = session.scalar(
        select(BillOccurrence)
        .options(joinedload(BillOccurrence.bill).joinedload(Bill.category),
                 joinedload(BillOccurrence.bill).joinedload(Bill.subcategory))
        .where(BillOccurrence.id == occurrence_id)
        .with_for_update(of=BillOccurrence)
    )
    if occurrence is None:
        raise NotFoundError("Bill occurrence does not exist.")
    if occurrence.status == "paid":
        raise ConflictError("Bill occurrence is already paid.")

    expense = Expense(
        transaction_date=paid_date,
        amount=paid_amount,
        category=occurrence.bill.category,
        subcategory=occurrence.bill.subcategory,
    )
    session.add(expense)
    session.flush()
    occurrence.status = "paid"
    occurrence.paid_amount = paid_amount
    occurrence.paid_date = paid_date
    occurrence.amount = paid_amount
    occurrence.expense_id = expense.id
    commit(session)
    return BillOccurrenceRead.model_validate(occurrence)


def _due_date_for_month(year: int, month: int, due_day: int | None) -> date:
    if due_day is None:
        raise ValueError("Monthly bill must have a due day.")
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(due_day, last_day))


def _next_month(month: date) -> date:
    if month.month == 12:
        return date(month.year + 1, 1, 1)
    return date(month.year, month.month + 1, 1)
