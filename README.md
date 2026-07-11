# tg-sales-assistant

Telegram-бот **Алексей** — AI-ассистент отдела продаж онлайн-школы «Финансист». Проводит квалификацию, подбирает курс и сохраняет заявки в Google Таблицу.

## Сценарий бота

1. **Приветствие** — представление и предложение подобрать курс
2. **Квалификация** — тест из 4 вопросов с выбором ответа кнопками
3. **Рекомендация** — подбор программы на основе ответов
4. **Вопросы** — отвечает на вопросы клиента, после каждого ответа спрашивает «Остались ли вопросы?»
5. **Сбор контактов** — имя и email для получения итога
6. **Google Таблица** — сохраняет имя, email, уровень, программу и ответы квалификации
7. **Уведомления менеджеру** — в Telegram при новой заявке или если нужен живой ответ

## База знаний

Цены и программы — в одном файле `knowledge/catalog.yaml`. Подробная инструкция для заказчика: [knowledge/README.md](knowledge/README.md).

```bash
python scripts/build_knowledge.py   # собрать generated/ из catalog.yaml
python scripts/reindex_knowledge.py # обновить векторный индекс в Supabase
```

```
knowledge/
├── catalog.yaml          # курсы, цены, пакеты — редактирует заказчик
├── faq.md                # гарантии, оплата, общие FAQ
└── generated/            # создаётся автоматически, не редактировать
```

## Структура проекта

```
tg-sales-assistant/
├── prompts/system.md
├── knowledge/catalog.yaml
├── knowledge/faq.md
├── knowledge/generated/            # автогенерация из catalog.yaml
├── scripts/build_knowledge.py
├── scripts/google-apps-script.js   # код для Google Таблицы
├── src/
│   ├── bot.py
│   ├── flow.py                     # сценарий диалога
│   ├── session.py
│   ├── sheets.py
│   └── ...
├── main.py
└── .env
```

## Запуск (продакшен)

Бот работает на **Fly.io**. Деплой автоматический при push в `main` через GitHub Actions.

1. Добавьте `FLY_API_TOKEN` в GitHub Secrets (см. [FLY_DEPLOY.md](FLY_DEPLOY.md))
2. Push в `main` → Actions задеплоит бот
3. **Не запускайте** `python main.py` локально — это вызовет конфликт с Fly

Панель: https://fly.io/apps/tg-sales-assistant

## Локальная разработка

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

Заполните `.env` (см. `.env.example`):

| Переменная | Описание |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Токен от [@BotFather](https://t.me/BotFather) |
| `GROQ_API_KEY` | Ключ от [console.groq.com/keys](https://console.groq.com/keys) |
| `GOOGLE_SHEETS_WEBHOOK_URL` | URL веб-приложения Apps Script |
| `MANAGER_TELEGRAM_CHAT_ID` | Telegram ID менеджера для уведомлений (узнать: [@userinfobot](https://t.me/userinfobot)) |

```bash
set ALLOW_LOCAL_RUN=1
python main.py
```

## Настройка Google Таблицы

1. Создайте [Google Таблицу](https://sheets.google.com)
2. **Расширения → Apps Script** — вставьте код из `scripts/google-apps-script.js`
3. Запустите функцию `setupSheet()` (один раз, разрешите доступ)
4. **Развернуть → Новое развертывание → Веб-приложение**
   - Запуск от: **Я**
   - Доступ: **Все**
5. Скопируйте URL развертывания в `GOOGLE_SHEETS_WEBHOOK_URL`

## Команды

| Команда | Описание |
|---|---|
| `/start` | Начать подбор курса |
| `/help` | Справка |
| `/reset` | Начать заново |

## Деплой на Fly.io

См. [FLY_DEPLOY.md](FLY_DEPLOY.md) — Dockerfile, `fly.toml` и пошаговая инструкция.
