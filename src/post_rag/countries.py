from __future__ import annotations

import json
from pathlib import Path

from post_rag.config import COUNTRIES_PATH
from post_rag.models import CountryConditions, ServiceCondition


class CountryRepository:
    def __init__(self, path: Path = COUNTRIES_PATH) -> None:
        self._countries = json.loads(path.read_text(encoding="utf-8"))
        self._by_code = {country["code"].upper(): country for country in self._countries}
        self._by_name = {country["name_ko"].replace(" ", ""): country for country in self._countries}

    def find(self, destination: str) -> CountryConditions | None:
        key = destination.strip()
        raw = self._by_code.get(key.upper()) or self._by_name.get(key.replace(" ", ""))
        if raw is None:
            return None
        services = [
            ServiceCondition(service=name, **condition)
            for name, condition in raw["services"].items()
        ]
        return CountryConditions(
            code=raw["code"],
            name_ko=raw["name_ko"],
            services=services,
            source_urls=raw["source_urls"],
            collected_at=raw["collected_at"],
        )

    def names(self) -> list[tuple[str, str]]:
        return [(country["code"], country["name_ko"]) for country in self._countries]

