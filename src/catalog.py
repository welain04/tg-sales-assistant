from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from src.config import settings


@dataclass(frozen=True)
class Program:
    id: str
    level: str
    title: str
    short_title: str
    price_rub: int
    audience: str
    result: str
    summary: str
    explanation: str
    duration: str
    format: str
    includes: str
    modules: tuple[str, ...]

    @property
    def price(self) -> str:
        return format_price_rub(self.price_rub)

    @property
    def price_text(self) -> str:
        return f"{self.price_rub} рублей"


@dataclass(frozen=True)
class Package:
    id: str
    title: str
    program_ids: tuple[str, ...]
    price_rub: int
    audience: str
    access_note: str | None

    @property
    def price(self) -> str:
        return format_price_rub(self.price_rub)

    @property
    def price_text(self) -> str:
        return f"{self.price_rub} рублей"


@dataclass(frozen=True)
class SchoolCatalog:
    school_name: str
    school_tagline: str
    manager_hint: str
    support_email: str
    installment_note: str
    programs: tuple[Program, ...]
    packages: tuple[Package, ...]

    def program_by_id(self, program_id: str) -> Program | None:
        return next((program for program in self.programs if program.id == program_id), None)

    def programs_by_ids(self, program_ids: tuple[str, ...]) -> tuple[Program, ...]:
        return tuple(
            program
            for program_id in program_ids
            if (program := self.program_by_id(program_id)) is not None
        )


def format_price_rub(amount: int) -> str:
    return f"{amount} ₽"


def _normalize_multiline(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return re.sub(r"\s+", " ", text)


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Некорректный формат каталога: {path}")
    return data


def load_catalog(catalog_path: Path | None = None) -> SchoolCatalog:
    path = catalog_path or (settings.knowledge_dir / "catalog.yaml")
    data = _load_yaml(path)

    school = data.get("school", {})
    contacts = school.get("contacts", {})
    installment = data.get("installment", {})

    programs: list[Program] = []
    for item in data.get("programs", []):
        programs.append(
            Program(
                id=str(item["id"]),
                level=_normalize_multiline(item["level"]),
                title=_normalize_multiline(item["title"]),
                short_title=_normalize_multiline(item.get("short_title") or item["title"]),
                price_rub=int(item["price_rub"]),
                audience=_normalize_multiline(item["audience"]),
                result=_normalize_multiline(item["result"]),
                summary=_normalize_multiline(item["summary"]),
                explanation=_normalize_multiline(item["explanation"]),
                duration=_normalize_multiline(item["duration"]),
                format=_normalize_multiline(item["format"]),
                includes=_normalize_multiline(item["includes"]),
                modules=tuple(_normalize_multiline(module) for module in item.get("modules", [])),
            )
        )

    packages: list[Package] = []
    for item in data.get("packages", []):
        packages.append(
            Package(
                id=str(item["id"]),
                title=_normalize_multiline(item["title"]),
                program_ids=tuple(str(program_id) for program_id in item["program_ids"]),
                price_rub=int(item["price_rub"]),
                audience=_normalize_multiline(item["audience"]),
                access_note=_normalize_multiline(item.get("access_note")) or None,
            )
        )

    return SchoolCatalog(
        school_name=_normalize_multiline(school.get("name", "Финансист")),
        school_tagline=_normalize_multiline(school.get("tagline", "")),
        manager_hint=_normalize_multiline(contacts.get("manager_hint", "")),
        support_email=_normalize_multiline(contacts.get("email", "")),
        installment_note=_normalize_multiline(installment.get("note", "")),
        programs=tuple(programs),
        packages=tuple(packages),
    )


@lru_cache(maxsize=1)
def get_catalog() -> SchoolCatalog:
    return load_catalog()


def get_programs() -> tuple[Program, ...]:
    return get_catalog().programs


def _normalize_program_name(name: str) -> str:
    normalized = name.strip().lower().replace("ё", "е")
    return re.sub(r"[«»\"'']", "", normalized)


def match_known_program(program_name: str) -> Program | None:
    normalized = _normalize_program_name(program_name)
    if not normalized:
        return None

    for program in get_programs():
        candidates = (
            _normalize_program_name(program.title),
            _normalize_program_name(program.short_title),
            _normalize_program_name(program.level),
        )
        if any(
            normalized == candidate or normalized in candidate or candidate in normalized
            for candidate in candidates
            if candidate
        ):
            return program
    return None
