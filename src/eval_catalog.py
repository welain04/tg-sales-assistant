from __future__ import annotations

from src.catalog import get_catalog

_PRICE_PREFIX = "@price:"


def expand_eval_keywords(keywords: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """Подставляет актуальные цены из catalog.yaml в тестовые ожидания."""
    catalog = get_catalog()
    program_prices = {program.id: str(program.price_rub) for program in catalog.programs}
    package_prices = {package.id: str(package.price_rub) for package in catalog.packages}

    expanded: list[str] = []
    for keyword in keywords:
        if not keyword.startswith(_PRICE_PREFIX):
            expanded.append(keyword)
            continue

        ref = keyword[len(_PRICE_PREFIX) :]
        if ref.startswith("package:"):
            package_id = ref.split(":", 1)[1]
            price = package_prices.get(package_id)
        else:
            price = program_prices.get(ref)

        if price is None:
            raise ValueError(f"Неизвестная ссылка на цену в тестах: {keyword}")

        expanded.append(price)

    return tuple(expanded)
