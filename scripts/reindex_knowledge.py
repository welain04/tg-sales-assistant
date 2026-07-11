#!/usr/bin/env python3
"""Индексация knowledge/ в Supabase pgvector.

Требования:
1. Выполнить SQL из supabase/migrations/001_knowledge_vectors.sql
2. Заполнить SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, OPENAI_API_KEY в .env

Примеры:
    python scripts/reindex_knowledge.py
    python scripts/reindex_knowledge.py --force
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.rag_index import reindex_knowledge


def main() -> int:
    parser = argparse.ArgumentParser(description="Индексация knowledge/ в Supabase pgvector")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Переиндексировать все файлы, даже если hash не изменился",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Подробные логи",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    try:
        stats = reindex_knowledge(force=args.force)
    except ValueError as exc:
        logging.error("%s", exc)
        return 1
    except Exception:
        logging.exception("Индексация завершилась с ошибкой")
        return 1

    print(
        "Готово: "
        f"файлов={stats.scanned_files}, "
        f"проиндексировано={stats.indexed_files}, "
        f"пропущено={stats.skipped_files}, "
        f"удалено={stats.removed_files}, "
        f"чанков={stats.total_chunks}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
