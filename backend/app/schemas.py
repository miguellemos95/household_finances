from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models import AMOUNT_PRECISION, AMOUNT_SCALE, NAME_LENGTH
from app.months import Month

MAX_ENTITY_ID = 2_147_483_647

Amount = Annotated[
    Decimal,
    Field(gt=0, max_digits=AMOUNT_PRECISION, decimal_places=AMOUNT_SCALE),
]
EntityId = Annotated[int, Field(ge=1, le=MAX_ENTITY_ID)]
MemberName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=NAME_LENGTH),
]


class ReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class NamedReference(ReadModel):
    id: int
    name: str


class CategoryRead(NamedReference):
    subcategories: list[NamedReference]


class MemberRead(NamedReference):
    pass


class MemberRename(BaseModel):
    name: MemberName


class ExpenseCreate(BaseModel):
    transaction_date: date
    amount: Amount
    category_id: EntityId
    subcategory_id: EntityId | None = None


class ExpenseRead(ReadModel):
    id: int
    transaction_date: date
    amount: Decimal
    category: NamedReference
    subcategory: NamedReference | None


class IncomeCreate(BaseModel):
    member_id: EntityId
    month: Month
    amount: Amount


class IncomeRead(ReadModel):
    id: int
    member_id: int
    month: Month
    amount: Decimal


class MemberIncome(BaseModel):
    member_id: int
    member_name: str
    amount: Decimal | None


class BudgetSet(BaseModel):
    amount: Amount


class CategoryBudgetRead(ReadModel):
    category: NamedReference
    month: Month
    limit: Decimal | None
    spent: Decimal
    percent: Decimal
    state: str


class MonthlySummary(BaseModel):
    month: Month
    incomes: list[MemberIncome]
    total_income: Decimal
    total_expenses: Decimal
    balance: Decimal
    category_budgets: list[CategoryBudgetRead]
