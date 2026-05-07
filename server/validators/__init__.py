"""Per-data-type validators."""

from __future__ import annotations

import re
from typing import Any

from dateutil import parser as dateparser


class _BaseValidator:
    data_type: str

    def validate(self, value: Any) -> tuple[bool, Any]:
        return True, value


class DateValidator(_BaseValidator):
    data_type = "date"

    def validate(self, value):
        if not value:
            return False, value
        try:
            dt = dateparser.parse(str(value), fuzzy=True)
            return True, dt.date().isoformat()
        except Exception:
            return False, value


class CurrencyValidator(_BaseValidator):
    data_type = "currency"
    _re = re.compile(r"(?:\$|USD|EUR|GBP|INR|€|£|¥)?\s?[\d,]+(?:\.\d{1,2})?", re.I)

    def validate(self, value):
        if value is None:
            return False, value
        return bool(self._re.search(str(value))), value


class NumberValidator(_BaseValidator):
    data_type = "number"

    def validate(self, value):
        try:
            cleaned = re.sub(r"[,\s]", "", str(value))
            return True, float(cleaned)
        except Exception:
            return False, value


class EmailValidator(_BaseValidator):
    data_type = "email"
    _re = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

    def validate(self, value):
        if not value:
            return False, value
        return bool(self._re.match(str(value).strip())), str(value).strip()


class PhoneValidator(_BaseValidator):
    data_type = "phone"
    _re = re.compile(r"^\+?[\d\s().\-]{7,}$")

    def validate(self, value):
        if not value:
            return False, value
        return bool(self._re.match(str(value).strip())), str(value).strip()


class IdValidator(_BaseValidator):
    data_type = "id"

    def validate(self, value):
        if not value:
            return False, value
        s = str(value).strip()
        return 3 <= len(s) <= 40 and re.match(r"^[A-Za-z0-9\-/_]+$", s) is not None, s


class PercentageValidator(_BaseValidator):
    data_type = "percentage"
    _re = re.compile(r"\d+(?:\.\d+)?\s*%")

    def validate(self, value):
        return bool(self._re.search(str(value))), value


class StringValidator(_BaseValidator):
    data_type = "string"

    def validate(self, value):
        if value is None:
            return False, value
        s = str(value).strip()
        return len(s) > 0, s


_VALIDATORS = {
    v.data_type: v
    for v in (
        DateValidator(),
        CurrencyValidator(),
        NumberValidator(),
        EmailValidator(),
        PhoneValidator(),
        IdValidator(),
        PercentageValidator(),
        StringValidator(),
    )
}


def validate(data_type: str, value: Any) -> tuple[bool, Any]:
    v = _VALIDATORS.get(data_type) or _VALIDATORS["string"]
    try:
        return v.validate(value)
    except Exception:
        return False, value
