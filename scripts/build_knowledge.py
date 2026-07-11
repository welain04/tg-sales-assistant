#!/usr/bin/env python3
"""Собирает базу знаний из knowledge/catalog.yaml.

Заказчик меняет цены и программы только в catalog.yaml.
Этот скрипт обновляет файлы в knowledge/generated/, которые читает бот.

Пример:
    python scripts/build_knowledge.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.catalog import Package, Program, SchoolCatalog, load_catalog

GENERATED_DIR = ROOT / "knowledge" / "generated"
AUTO_HEADER = (
    "# Автоматически сгенерировано из knowledge/catalog.yaml\n"
    "# Не редактируйте вручную — изменения будут перезаписаны.\n"
    "# Запуск: python scripts/build_knowledge.py\n\n"
)


def _program_block(program: Program) -> str:
    lines = [
        f'Уровень: "{program.level}"',
        f"Для кого: {program.audience}",
        f'Продукт: "{program.title}"',
        f"Тезисно, какие результаты даст продукт: {program.result}",
        f"Цена: {program.price_text}",
        f"Длительность: {program.duration}",
        f"Формат: {program.format}",
        f"Что входит в стоимость: {program.includes}",
    ]
    return "\n".join(lines)


def build_products_txt(catalog: SchoolCatalog) -> str:
    blocks = [_program_block(program) for program in catalog.programs]
    return "\n\n".join(blocks) + "\n"


def build_catalog_md(catalog: SchoolCatalog) -> str:
    lines = [
        AUTO_HEADER.rstrip(),
        "## Каталог программ и цены",
        "",
        (
            "В школе четыре основные программы, выстроенные по уровню подготовки "
            "клиента — от полного нуля до работы с уже сформированным капиталом."
        ),
        "",
    ]

    for program in catalog.programs:
        lines.append(_program_block(program))
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Программы курсов по модулям")
    lines.append("")

    for program in catalog.programs:
        lines.append(f"{program.title} — программа:")
        for module in program.modules:
            lines.append(module)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _package_program_titles(catalog: SchoolCatalog, package: Package) -> str:
    programs = catalog.programs_by_ids(package.program_ids)
    return " + ".join(f"«{program.short_title}»" for program in programs)


def _package_full_price(catalog: SchoolCatalog, package: Package) -> int:
    return sum(program.price_rub for program in catalog.programs_by_ids(package.program_ids))


def build_packages_md(catalog: SchoolCatalog) -> str:
    lines = [
        AUTO_HEADER.rstrip(),
        "## Пакеты из нескольких курсов",
        "",
        "Школа предлагает готовые пакеты со скидкой при единовременной оплате.",
        "",
    ]

    for package in catalog.packages:
        full_price = _package_full_price(catalog, package)
        savings = max(full_price - package.price_rub, 0)
        line = (
            f"Пакет «{package.title}» — курсы {_package_program_titles(catalog, package)}. "
            f"Полная стоимость по отдельности: {full_price} рублей. "
            f"Цена пакета: {package.price_rub} рублей. "
            f"Экономия: {savings} рублей."
        )
        if package.access_note:
            line += f" {package.access_note}"
        line += f" Для кого: {package.audience}"
        lines.append(line)
        lines.append("")

    if catalog.installment_note:
        lines.append(catalog.installment_note)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_price_faq_md(catalog: SchoolCatalog) -> str:
    lines = [
        AUTO_HEADER.rstrip(),
        "## Частые вопросы о программах и ценах",
        "",
    ]

    price_list = ", ".join(
        f"«{program.short_title}» ({program.price_rub} рублей)"
        for program in catalog.programs
    )
    max_package_savings = 0
    if catalog.packages:
        max_package_savings = max(
            _package_full_price(catalog, package) - package.price_rub
            for package in catalog.packages
        )

    lines.extend(
        [
            "Вопрос: Какие программы есть в школе «Финансист»?",
            (
                f"Ответ: В школе «{catalog.school_name}» четыре основные программы: {price_list}. "
                f"Также есть пакеты со скидкой до {max_package_savings} рублей."
            ),
            "",
        ]
    )

    for program in catalog.programs:
        lines.extend(
            [
                f"Вопрос: Сколько стоит {program.title}?",
                (
                    f"Ответ: {program.title} стоит {program.price_rub} рублей. "
                    f"Длительность — {program.duration}. "
                    f"В стоимость входят: {program.includes}"
                ),
                "",
            ]
        )

    first_program = catalog.programs[0]
    first_package = catalog.packages[0] if catalog.packages else None
    newbie_answer = (
        f"Ответ: Начните с «{first_program.title}» за {first_program.price_rub} рублей. "
        f"{first_program.result}"
    )
    if first_package:
        newbie_answer += (
            f" Если хотите сразу выстроить бюджет и дельту — пакет "
            f"«{first_package.title}» за {first_package.price_rub} рублей."
        )
    lines.extend(
        [
            "Вопрос: Какой курс выбрать новичку без опыта в финансах?",
            newbie_answer,
            "",
        ]
    )

    package_lines = [
        f"«{package.title}» — {package.price_rub} рублей"
        for package in catalog.packages
    ]
    lines.extend(
        [
            "Вопрос: Есть ли пакеты из нескольких курсов?",
            "Ответ: Да. " + "; ".join(package_lines) + ". "
            "Подробности и рассрочку уточняйте у менеджера.",
            "",
        ]
    )

    for package in catalog.packages:
        lines.extend(
            [
                f"Вопрос: Сколько стоит пакет «{package.title}»?",
                (
                    f"Ответ: Пакет «{package.title}» стоит {package.price_rub} рублей "
                    f"вместо {_package_full_price(catalog, package)} рублей по отдельности. "
                    f"Включает: {_package_program_titles(catalog, package)}."
                ),
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_knowledge(catalog_path: Path | None = None) -> list[Path]:
    catalog = load_catalog(catalog_path)
    outputs = {
        GENERATED_DIR / "products.txt": build_products_txt(catalog),
        GENERATED_DIR / "catalog.md": build_catalog_md(catalog),
        GENERATED_DIR / "packages.md": build_packages_md(catalog),
        GENERATED_DIR / "price_faq.md": build_price_faq_md(catalog),
    }

    for path, content in outputs.items():
        write_text(path, content)

    return list(outputs)


def main() -> int:
    written = build_knowledge()
    print("База знаний собрана из knowledge/catalog.yaml:")
    for path in written:
        print(f"  - {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
