from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, UniqueConstraint, false, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

NAME_LENGTH = 50
AMOUNT_PRECISION = 12
AMOUNT_SCALE = 2


class Base(DeclarativeBase):
    pass


class Member(Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(NAME_LENGTH))


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("name", name="uq_categories_name"),
        Index(
            "uq_categories_one_bill_category",
            "is_bill_category",
            unique=True,
            postgresql_where=text("is_bill_category"),
            sqlite_where=text("is_bill_category"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(NAME_LENGTH))
    position: Mapped[int]
    is_bill_category: Mapped[bool] = mapped_column(server_default=false())
    subcategories: Mapped[list["Subcategory"]] = relationship(order_by="Subcategory.position")


class Subcategory(Base):
    __tablename__ = "subcategories"
    __table_args__ = (
        UniqueConstraint("category_id", "name", name="uq_subcategories_category_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    name: Mapped[str] = mapped_column(String(NAME_LENGTH))
    position: Mapped[int]


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_date: Mapped[date] = mapped_column(index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(AMOUNT_PRECISION, AMOUNT_SCALE))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    subcategory_id: Mapped[int | None] = mapped_column(ForeignKey("subcategories.id"))
    category: Mapped[Category] = relationship()
    subcategory: Mapped[Subcategory | None] = relationship()


class Income(Base):
    __tablename__ = "incomes"
    __table_args__ = (
        UniqueConstraint("member_id", "month", name="uq_incomes_member_month"),
        CheckConstraint("amount > 0", name="ck_incomes_amount_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"))
    month: Mapped[date]
    amount: Mapped[Decimal] = mapped_column(Numeric(AMOUNT_PRECISION, AMOUNT_SCALE))


class CategoryBudget(Base):
    __tablename__ = "category_budgets"
    __table_args__ = (
        UniqueConstraint("category_id", "month", name="uq_category_budgets_category_month"),
        CheckConstraint("amount > 0", name="ck_category_budgets_amount_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    month: Mapped[date]
    amount: Mapped[Decimal] = mapped_column(Numeric(AMOUNT_PRECISION, AMOUNT_SCALE))


class Bill(Base):
    __tablename__ = "bills"
    __table_args__ = (
        CheckConstraint(
            "(recurrence = 'one_off' AND due_day IS NULL) OR "
            "(recurrence = 'monthly' AND due_day BETWEEN 1 AND 31)",
            name="ck_bills_recurrence",
        ),
        CheckConstraint("default_amount > 0", name="ck_bills_amount_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    recurrence: Mapped[str] = mapped_column(String(20))
    first_due_date: Mapped[date] = mapped_column(index=True)
    due_day: Mapped[int | None]
    default_amount: Mapped[Decimal] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE)
    )
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    subcategory_id: Mapped[int | None] = mapped_column(ForeignKey("subcategories.id"))
    category: Mapped[Category] = relationship()
    subcategory: Mapped[Subcategory | None] = relationship()
    occurrences: Mapped[list["BillOccurrence"]] = relationship(
        back_populates="bill", cascade="all, delete-orphan"
    )


class BillOccurrence(Base):
    __tablename__ = "bill_occurrences"
    __table_args__ = (
        UniqueConstraint("bill_id", "due_date", name="uq_bill_occurrences_bill_due"),
        CheckConstraint("amount > 0", name="ck_bill_occurrences_amount_positive"),
        CheckConstraint("paid_amount IS NULL OR paid_amount > 0",
                        name="ck_bill_occurrences_paid_amount_positive"),
        CheckConstraint(
            "(status IN ('pending', 'overdue') AND paid_amount IS NULL AND paid_date IS NULL) OR "
            "(status = 'paid' AND paid_amount IS NOT NULL AND paid_date IS NOT NULL)",
            name="ck_bill_occurrences_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    bill_id: Mapped[int] = mapped_column(ForeignKey("bills.id"))
    due_date: Mapped[date] = mapped_column(index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(AMOUNT_PRECISION, AMOUNT_SCALE))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    paid_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(AMOUNT_PRECISION, AMOUNT_SCALE)
    )
    paid_date: Mapped[date | None] = mapped_column(index=True)
    expense_id: Mapped[int | None] = mapped_column(
        ForeignKey("expenses.id"), unique=True
    )
    bill: Mapped[Bill] = relationship(back_populates="occurrences")
