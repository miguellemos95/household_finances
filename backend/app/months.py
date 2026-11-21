import calendar
import re
from datetime import date
from typing import Annotated

from pydantic import BeforeValidator, PlainSerializer, WithJsonSchema

MONTH_PATTERN = r"^[1-9]\d{3}-(0[1-9]|1[0-2])$"


def parse_month(value: object) -> date:
    if isinstance(value, date):
        return value.replace(day=1)
    if not isinstance(value, str) or re.fullmatch(MONTH_PATTERN, value) is None:
        raise ValueError("Month must use the YYYY-MM format.")
    year, month = value.split("-")
    return date(int(year), int(month), 1)


def format_month(value: date) -> str:
    return f"{value.year:04d}-{value.month:02d}"


def month_bounds(month: date) -> tuple[date, date]:
    last_day = calendar.monthrange(month.year, month.month)[1]
    return month.replace(day=1), month.replace(day=last_day)


# A calendar month, exchanged as "YYYY-MM" and held as the first day of that month.
Month = Annotated[
    date,
    BeforeValidator(parse_month),
    PlainSerializer(format_month, return_type=str),
    WithJsonSchema({"type": "string", "pattern": MONTH_PATTERN, "examples": ["2025-11"]}),
]
