import os
import sys


def _ensure_allowed_runtime() -> None:
    if os.getenv("FLY_APP_NAME"):
        return
    if os.getenv("ALLOW_LOCAL_RUN") == "1":
        return
    print(
        "Локальный запуск отключён. Бот работает на Fly.io через GitHub Actions.\n"
        "Деплой: push в main.\n"
        "Для локальной отладки: set ALLOW_LOCAL_RUN=1"
    )
    sys.exit(1)


if __name__ == "__main__":
    _ensure_allowed_runtime()
    from src.bot import main

    main()
