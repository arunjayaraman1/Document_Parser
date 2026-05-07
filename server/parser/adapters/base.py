"""FileAdapter base — every parser implements this."""

from __future__ import annotations

from abc import ABC, abstractmethod
from server.core.document import Document


class BaseFileAdapter(ABC):
    name: str = "base"
    accepts: set[str] = set()

    @abstractmethod
    def parse(self, path: str) -> Document:
        ...
