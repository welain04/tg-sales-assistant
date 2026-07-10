# Деплой на Fly.io

Telegram-бот работает в режиме **long polling** — на Fly.io должен быть запущен **ровно один** процесс.

## Что понадобится

- Аккаунт на [fly.io](https://fly.io)
- Установленный [flyctl](https://fly.io/docs/hands-on/install-flyctl/)
- Git-репозиторий с проектом (или деплой из локальной папки)
- Заполненный локальный `.env` — секреты перенесёте на Fly

## Шаг 1. Установить flyctl

**Windows (PowerShell):**
```powershell
powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"
```

Проверка:
```bash
fly version
```

## Шаг 2. Войти в Fly.io

```bash
fly auth login
```

## Шаг 3. Остановить локальный бот

Перед деплоем **обязательно** остановите бота на своём компьютере.  
Два процесса с одним токеном дают ошибку `409 Conflict`.

## Шаг 4. Создать приложение

Из корня проекта:

```bash
cd tg-sales-assistant
fly launch --no-deploy
```

При вопросах flyctl:

- **Имя приложения** — можно оставить `tg-sales-assistant` или своё (тогда обновите `app` в `fly.toml`)
- **Регион** — `fra` (Frankfurt) или `ams` (Amsterdam)
- **PostgreSQL / Redis** — **No**
- **Deploy now** — **No** (мы сначала зададим секреты)

Если приложение уже создано, этот шаг пропустите.

## Шаг 5. Задать секреты

Подставьте значения из своего `.env`:

```bash
fly secrets set ^
  TELEGRAM_BOT_TOKEN="ваш_токен" ^
  GROQ_API_KEY="ваш_ключ_groq" ^
  GOOGLE_SHEETS_WEBHOOK_URL="ваш_url_apps_script" ^
  MANAGER_TELEGRAM_CHAT_ID="ваш_chat_id"
```

**Linux / macOS:**
```bash
fly secrets set \
  TELEGRAM_BOT_TOKEN="ваш_токен" \
  GROQ_API_KEY="ваш_ключ_groq" \
  GOOGLE_SHEETS_WEBHOOK_URL="ваш_url_apps_script" \
  MANAGER_TELEGRAM_CHAT_ID="ваш_chat_id"
```

Проверка:
```bash
fly secrets list
```

## Шаг 6. Задеплоить

```bash
fly deploy --depot=false --ha=false
```

Если сборка через Depot зависает (`deadline_exceeded`), используйте `--depot=false` — сборка пойдёт через Fly remote builder.

## Шаг 7. Оставить один инстанс

```bash
fly scale count 1
```

Повторно после каждого деплоя, если Fly поднял больше машин.

## Шаг 8. Проверить логи

```bash
fly logs
```

Ожидаемые строки:
```
Loaded 4 knowledge chunks from ...
Bot is starting...
Application started
```

Ошибки `409 Conflict` означают, что бот запущен ещё где-то (локально или второй машиной на Fly).

## Шаг 9. Протестировать бота

В Telegram:

1. `/start` — приветствие и тест с кнопками
2. Пройти тест до конца
3. Имя + email — заявка в Google Таблице
4. «какие есть программы?» — ответ из каталога
5. «менеджер» — уведомление менеджеру (менеджер должен был написать боту `/start`)

## Обновление после изменений в коде

```bash
git pull
fly deploy
fly scale count 1
fly logs
```

## Полезные команды

| Команда | Описание |
|---|---|
| `fly status` | Статус приложения |
| `fly logs` | Логи в реальном времени |
| `fly ssh console` | Зайти в контейнер |
| `fly apps restart tg-sales-assistant` | Перезапуск |
| `fly secrets set KEY=value` | Обновить секрет |
| `fly scale count 0` | Остановить (для отладки локально) |
| `fly scale count 1` | Снова запустить |

## Стоимость

Минимальная машина `shared-cpu-1x` + 256 MB — ориентир **~$3–5/мес**.  
Актуальные цены: [fly.io/docs/about/pricing](https://fly.io/docs/about/pricing)

## Частые проблемы

| Проблема | Решение |
|---|---|
| `409 Conflict` | Остановить локальный бот и `fly scale count 1` |
| Бот не отвечает | `fly logs`, проверить `TELEGRAM_BOT_TOKEN` |
| Нет заявок в таблице | Проверить `GOOGLE_SHEETS_WEBHOOK_URL` |
| Менеджер не получает сообщения | Менеджер написал боту `/start`; проверить `MANAGER_TELEGRAM_CHAT_ID` |
| Groq 429 | Подождать сброс лимита или сменить модель в `fly.toml` → `fly deploy` |
