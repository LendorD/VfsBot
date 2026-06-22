# Передача проекта: Telegram-бот записи на визу VFS Global

> Этот файл — контекст для ИИ-ассистента. Прочитай его целиком перед началом
> работы. Здесь описано, что уже сделано, что осталось реализовать и какие
> правила соблюдать.

## Что это за проект

Telegram-бот, который принимает от пользователя заявки на запись в визовый
центр **VFS Global** (диапазон дат + персональные данные), хранит их в
**PostgreSQL** и через **браузерную автоматизацию (Playwright)** периодически
проверяет свободные слоты, бронирует подходящий и уведомляет пользователя.

Репозиторий: https://github.com/LendorD/VfsBot.git

## Стек и соглашения (соблюдать строго)

- Python **3.11+**, стиль **PEP8 / Clean Code**.
- **aiogram 3.x** (Telegram), **SQLAlchemy 2.0 async** + **asyncpg** (БД),
  **Playwright** (браузер), **APScheduler** (планировщик),
  **loguru** (логи), **pydantic-settings** (конфиг из `.env`).
- Все функции/классы — с **docstring на русском**, **type hints** обязательны.
- Все I/O — **async/await**. Логи — структурированные, на русском.
- Конфигурация — только через `.env` (см. `.env.example`).

## Структура и статус по файлам

```
main.py                  ✅ запуск БД, браузера, планировщика, бота, graceful shutdown
bot/
  dispatcher.py          ✅ фабрики Bot/Dispatcher, внедрение БД, меню команд
  states.py              ✅ FSM-состояния /add и /edit
  keyboards.py           ✅ inline-клавиатуры
  handlers/
    start.py             ✅ /start, /help
    add.py               ✅ /add — пошаговый сбор + подтверждение
    status.py            ✅ /status
    edit.py              ✅ /edit
    cancel.py            ✅ /cancel
browser/
  manager.py             ✅ жизненный цикл Playwright и контекстов
  client.py              ⚠️ КАРКАС со стабами — главная зона работы
  selectors.py           ⚠️ селекторы-заглушки
  captcha_solver.py      ⚠️ интерфейс + стаб (бросает CaptchaError)
storage/
  models.py              ✅ User, Application, Session
  database.py            ✅ CRUD (async)
scheduler/
  checker.py             ✅ периодическая проверка/бронирование/уведомление
utils/
  config.py logger.py validators.py exceptions.py   ✅ полностью готовы
tests/
  test_validators.py     ✅ 16 тестов, проходят
  test_client.py         ✅ тесты структур и стаба капчи
```

## Что осталось реализовать (приоритеты)

### 1. Браузерный клиент VFS — `browser/client.py` (ГЛАВНОЕ)

Сейчас это документированный каркас. Методы помечены `TODO` и бросают
исключения-заглушки. Нужно реализовать реальный сценарий под **конкретный
визовый центр и страну подачи**:

- `_open_booking_page()` — переход на сайт, авторизация (логин/пароль из
  `.env`), выбор визового центра и категории визы, обработка капчи.
- `_scan_calendar(start_date, end_date)` — обойти календарь, вернуть первый
  свободный слот в диапазоне (или `None`).
- `_select_slot(slot)` — кликнуть день и время.
- `_fill_applicant_form(applicant)` — заполнить форму персональных данных.
- `_confirm_booking(slot)` — подтвердить и считать номер бронирования.

Для этого нужно через **DevTools на реальном сайте** определить актуальные
CSS/XPath-селекторы и вписать их в `browser/selectors.py` (там сейчас
осмысленные, но вымышленные значения).

### 2. Решение капчи — `browser/captcha_solver.py`

Сейчас `StubCaptchaSolver` бросает `CaptchaError`. Если потребуется —
реализовать `CaptchaSolver` поверх внешнего сервиса распознавания, выбирать
реализацию в `get_captcha_solver()` по наличию `CAPTCHA_API_KEY`.

### 3. Сохранение сессии — модель `storage/models.Session` уже есть

Реализовать сохранение/восстановление cookies и localStorage между
запусками, чтобы не проходить авторизацию и капчу каждый раз. Использовать
`BrowserManager.new_context(storage_state=...)`.

### 4. Инфраструктура (по желанию)

- **Alembic**-миграции вместо `create_all` (зависимость уже в requirements).
- **Dockerfile** + `docker-compose.yml` (бот + PostgreSQL).
- **Шифрование** чувствительных полей заявки (паспорт, email) в БД.
- Возможность прервать FSM-диалог `/add` на любом шаге (сейчас выйти можно
  только дойдя до подтверждения и нажав «Отменить»).

## Как запустить и проверить

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env          # заполнить BOT_TOKEN, DATABASE_URL и пр.
python main.py                # таблицы создаются автоматически
pytest                        # юнит-тесты
```

## Важное предупреждение

Автоматизация записи и обход капчи могут нарушать Условия использования
VFS Global и применимое законодательство. Перед реальным запуском это нужно
проверить. Бизнес-логика бота, БД и FSM — нейтральная инфраструктура; вся
специфика VFS изолирована в каталоге `browser/`.

## С чего начать ассистенту

1. Прочитай `README.md` и этот файл.
2. Изучи `browser/client.py` и `browser/selectors.py` — основная работа там.
3. Спроси у меня: страну подачи, тип визы и есть ли доступ к личному кабинету
   VFS — без этого реальные селекторы не определить.
```
