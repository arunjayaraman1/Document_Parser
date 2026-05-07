"""Tiny plugin registry — adapters/detectors/extractors register here at import time."""

from __future__ import annotations

from typing import Any

_REG: dict[str, list[Any]] = {
    "adapters": [],
    "schema_detectors": [],
    "extractors": [],
    "validators": {},
}


def register_adapter(adapter) -> None:
    _REG["adapters"].append(adapter)


def register_schema_detector(detector) -> None:
    _REG["schema_detectors"].append(detector)


def register_extractor(extractor) -> None:
    _REG["extractors"].append(extractor)


def register_validator(validator) -> None:
    _REG["validators"][validator.data_type] = validator


def adapters() -> list:
    return list(_REG["adapters"])


def schema_detectors() -> list:
    return list(_REG["schema_detectors"])


def extractors() -> list:
    return list(_REG["extractors"])


def validator_for(data_type: str):
    return _REG["validators"].get(data_type)
