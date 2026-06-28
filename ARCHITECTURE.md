# Архитектура проекта VfsBot

Telegram-бот для отслеживания и автоматического бронирования свободных
слотов записи в визовый центр **VFS Global**. Пользователь через диалог в
Telegram создаёт заявку (диапазон дат + персональные данные), бот хранит её
в **PostgreSQL** и фоновым планировщиком периодически проверяет сайт VFS
через браузерную автоматизацию (**Playwright**). При нахождении слота бот
пытается оформить запись и уведомляет пользователя.

> **Статус.** Вся инфраструктура (бот, БД, FSM, планировщик, валидация,
> логирование) готова и покрыта тестами. Браузерный слой взаимодействия с
> VFS (`browser/client.py`, `browser/selectors.py`, `browser/captcha_solver.py`)
> намеренно оставлен **каркасом со стабами** — это главная незавершённая зона.

---

## 1. Технологический стек

| Слой | Технология | Версия |
|------|------------|--------|
| Язык | Python | 3.11+ |
| Telegram | aiogram (FSM, роутеры) | 3.13.1 |
| База данных | PostgreSQL + SQLAlchemy 2.0 async + asyncpg | 2.0.35 / 0.29.0 |
| Миграции | Alembic (зависимость есть, не используется) | 1.13.2 |
| Планировщик | APScheduler (AsyncIOScheduler) | 3.10.4 |
| Браузер | Playwright (async, Chromium) | 1.47.0 |
| Конфигурация | pydantic-settings (`.env`) | 2.5.2 |
| Логи | loguru | 0.7.2 |
| Тесты | pytest + pytest-asyncio | 8.3.3 |
| Линтер | ruff (line-length 88, target py311) | — |

Соглашения: весь I/O — `async/await`; docstring на русском; обязательные
type hints; конфигурация только через `.env`; стиль PEP8 / Clean Code.

---

## 2. Карта каталогов

```
VfsBot/
├── main.py                 # Точка входа: запуск Telegram-бота
├── run_check.py            # Автономная проверка слотов без бота
├── core/                   # Ядро: общие модули без доменной логики (бывш. utils/)
│   ├── config.py           # Settings (pydantic-settings) + get_settings()
│   ├── logger.py           # Настройка loguru (консоль + файл с ротацией)
│   ├── validators.py       # Валидация дат, email, телефона, имени, паспорта
│   └── exceptions.py       # Иерархия кастомных исключений
├── captcha/                # Решение капчи (логика сопровождается отдельно)
│   └── solver.py           # Решатель капчи (бывш. browser/captcha_solver.py)
├── vfs_site/               # Взаимодействие с сайтом VFS (Playwright)
│   ├── browser.py          # Жизненный цикл браузера и контекстов  ✅
│   ├── session.py          # Персистентные сессии (cookies/localStorage)  ✅
│   ├── selectors.py        # CSS/XPath-селекторы сайта VFS          ⚠️ ЗАГЛУШКИ
│   └── client.py           # Клиент VFS: поиск/бронирование слотов  ⚠️ КАРКАС
├── telegram_bot/           # Telegram-слой (aiogram, бывш. bot/)
│   ├── dispatcher.py       # Фабрики Bot/Dispatcher, DI, меню команд
│   ├── states.py           # FSM-состояния /add и /edit
│   ├── keyboards.py        # Inline-клавиатуры и callback-префиксы
│   └── handlers/           # /start /help /add /status /edit /cancel
├── storage/                # Слой данных
│   ├── models.py           # SQLAlchemy-модели: User, Application, Session
│   └── database.py         # CRUD-операции (async)
├── scheduler/
│   └── checker.py          # APScheduler: периодическая проверка слотов
└── tests/                  # Юнит-тесты
```

Условные обозначения: ✅ готово, ⚠️ требует реализации.

---

## 3. Поток данных (общая схема)

```
Пользователь (Telegram)
        │  команды /add /status /edit /cancel
        ▼
   bot/handlers/*  ──FSM──▶  bot/states.py
        │  валидация (utils/validators.py)
        ▼
   storage/database.py  ◀──▶  PostgreSQL (storage/models.py)
        ▲                                  │
        │ читает активные заявки           │ статусы заявок
        │                                  ▼
scheduler/checker.py ──вызывает──▶ browser/client.py (VFSClient)
        │                                  │
        │                                  ▼
        │                          browser/manager.py ──▶ Playwright/Chromium ──▶ сайт VFS
        │                                  │
        │                          browser/captcha_solver.py (при капче)
        ▼
   notifier (main.make_notifier) ──▶ bot.send_message ──▶ Пользователь
```

Ключевая идея разделения: **бизнес-логика (бот, БД, FSM, планировщик) —
нейтральная инфраструктура; вся специфика VFS изолирована в каталоге
`browser/`.** Это позволяет дорабатывать рискованную часть, не трогая
остальной код.

---

## 4. Жизненный цикл приложения (`main.py`)

`main()` — единая асинхронная точка входа, запускающая компоненты в строгом
порядке:

1. `setup_logger()` — конфигурация loguru.
2. `get_settings()` — загрузка `.env`.
3. `Database(...)` + `create_tables()` — подключение к БД и создание таблиц
   (`Base.metadata.create_all`).
4. `BrowserManager().start()` — запуск Playwright и Chromium.
5. `get_captcha_solver(...)` + `VFSClient(...)` — создание клиента VFS.
6. `create_bot()`, `create_dispatcher(database)`, `setup_bot_commands()` —
   бот, диспетчер с внедрённой БД и меню команд.
7. `SlotChecker(...).start()` — запуск фонового планировщика.
8. `dispatcher.start_polling(bot)` — long polling (блокирует до остановки).

В блоке `finally` выполняется **graceful shutdown**: остановка планировщика,
браузера, пула БД и сессии бота. Сигналы `KeyboardInterrupt`/`SIGTERM`
обрабатываются на уровне `asyncio.run`.

---

## 5. Telegram-слой (`bot/`)

**`dispatcher.py`.** Фабрики `create_bot` (HTML-разметка по умолчанию) и
`create_dispatcher`. Зависимость `Database` внедряется через
`dispatcher["db"] = database` и автоматически прокидывается в любой хендлер,
объявивший параметр `db: Database`. FSM-хранилище — `MemoryStorage`
(состояния не переживают перезапуск процесса). Роутеры регистрируются из
списка `bot.handlers.routers`. `setup_bot_commands` ставит меню команд.

**`states.py`.** Две группы FSM-состояний:
- `AddApplication` — 10 шагов: даты → фамилия → имя → дата рождения →
  паспорт → дата выдачи → дата окончания → email → телефон → подтверждение.
- `EditApplication` — 3 шага: выбор заявки → выбор поля → ввод значения.

**`keyboards.py`.** Inline-клавиатуры. Callback-данные кодируются строками с
префиксами: `confirm:yes/no`, `app:<id>`, `field:<key>`, `cancel:<id>`.
Словарь `EDITABLE_FIELDS` задаёт набор редактируемых полей и их подписи.

**Хендлеры (`handlers/`):**
- `start.py` — `/start` (приветствие + список команд), `/help` (справка).
- `add.py` — пошаговый сбор заявки. Каждый шаг валидирует ввод; при ошибке
  просит повторить, не сбрасывая состояние. Финал — сводка с кнопками
  «Подтвердить»/«Отменить»; при подтверждении заявка пишется в БД.
- `status.py` — `/status`: список всех заявок пользователя с человекочитаемым
  статусом; для статуса `booked` показывает дату, время и номер брони.
- `edit.py` — `/edit`: выбор активной заявки → выбор поля → ввод нового
  значения (та же валидация, что и в `/add`). После изменения статус заявки
  сбрасывается в `WAITING`, чтобы перезапустить поиск.
- `cancel.py` — `/cancel`: список активных заявок → удаление выбранной из БД.

---

## 6. Слой данных (`storage/`)

**`models.py`** — три таблицы (декларативный стиль SQLAlchemy 2.0):

- **`users`** — `id`, `telegram_id` (BigInteger, unique, indexed),
  `username`, `created_at`. Связь one-to-many с заявками
  (`cascade="all, delete-orphan"`).
- **`applications`** — основная сущность: диапазон дат (`start_date`,
  `end_date`), `status` (enum), персональные данные (фамилия, имя, дата
  рождения, паспорт + даты выдачи/окончания, email, телефон), реквизиты
  найденной брони (`booked_date`, `booked_time`, `booking_reference`),
  `created_at`/`updated_at`.
- **`sessions`** — `cookies` (JSONB), `local_storage` (JSONB),
  `created_at`, `expires_at`. Предназначена для сохранения сессии браузера,
  **но пока не используется кодом**.

Статусы заявки (`ApplicationStatus`): `waiting`, `searching`, `found`,
`booked`, `error`, `cancelled`. Словарь `STATUS_LABELS_RU` даёт русские
подписи для сообщений бота.

**`database.py`** — класс `Database`: создаёт async-движок и фабрику сессий
(`expire_on_commit=False`, `pool_pre_ping=True`). Сессия открывается
отдельно на каждую операцию — безопасно при конкурентном доступе бота и
планировщика. Методы:
`create_tables`, `dispose`, `get_or_create_user`, `create_application`,
`get_application`, `get_user_applications` (с фильтром `only_active`),
`get_active_applications` (для планировщика, с жадной подгрузкой `user`
через `selectinload`), `update_application`, `set_status`, `mark_booked`,
`delete_application`. Ошибки оборачиваются в доменные исключения
(`DatabaseError`, `ApplicationNotFoundError`).

---

## 7. Браузерный слой (`browser/`) — главная зона доработки

**`manager.py` (✅ готов).** `BrowserManager` инкапсулирует жизненный цикл
Playwright: `start()` запускает Chromium с флагами анти-детекта
(`--disable-blink-features=AutomationControlled`, `--no-sandbox`),
`stop()` корректно закрывает ресурсы, `new_context(storage_state=...)`
создаёт изолированный контекст (свой User-Agent, локаль `ru-RU`, таймаут из
настроек, опциональное восстановление сессии). Поддерживает протокол
асинхронного контекстного менеджера. Принцип: один браузер на процесс,
отдельный контекст на заявку.

**`client.py` (⚠️ КАРКАС).** `VFSClient` — клиент сайта VFS. Публичный API:
- `find_slot(start, end)` — найти первый свободный слот в диапазоне.
- `book_slot(applicant, start, end)` — найти слот и выполнить полную запись.

Возвращает датаклассы `AvailableSlot(slot_date, slot_time)` и
`BookingResult(slot_date, slot_time, reference)`.

Внутренние шаги-стабы (помечены `TODO`, требуют реальной реализации под
конкретный визовый центр/страну):
- `_open_booking_page(page)` — переход на сайт, авторизация, выбор центра и
  категории визы, обработка капчи. **Сейчас бросает `VFSClientError`.**
- `_scan_calendar(page, start, end)` — обход календаря, фильтр по диапазону.
  **Сейчас возвращает `None`.**
- `_select_slot(page, slot)` — клик по дню и времени. **Пустой стаб.**
- `_fill_applicant_form(page, applicant)` — заполнение формы. **Пустой стаб.**
- `_confirm_booking(page, slot)` — подтверждение, чтение номера брони.
  **Сейчас бросает `BookingError`.**

**`selectors.py` (⚠️ ЗАГЛУШКИ).** Датаклассы с CSS/XPath-селекторами
(`LoginSelectors`, `BookingSelectors`, `ApplicantFormSelectors`,
`CaptchaSelectors`, `ConfirmationSelectors`) и их готовые экземпляры
(`LOGIN`, `BOOKING`, `APPLICANT_FORM`, `CAPTCHA`, `CONFIRMATION`). Значения
осмысленные, но **вымышленные** — реальные нужно определить через DevTools.

**`captcha_solver.py` (⚠️ СТАБ).** Абстрактный `CaptchaSolver` с методами
`solve_image_captcha` и `solve_recaptcha`. Реализация `StubCaptchaSolver`
всегда бросает `CaptchaError`. Фабрика `get_captcha_solver(api_key)` пока
всегда возвращает заглушку (выбор реальной реализации по `api_key` — TODO).

---

## 8. Планировщик (`scheduler/checker.py`)

`SlotChecker` на базе `AsyncIOScheduler`. `start()` регистрирует job с
интервалом `CHECK_INTERVAL_SECONDS` (`max_instances=1`, `coalesce=True` —
прогоны не накладываются и схлопываются при пропуске).

Прогон `_check_all()`: читает активные заявки (`WAITING`, `SEARCHING`) и
обрабатывает каждую через `_process_application()`. Защита от двойной
обработки — множество `_in_progress`.

`_process_application()` для одной заявки:
1. Статус → `SEARCHING`.
2. Сбор словаря заявителя (`_build_applicant_dict`).
3. `vfs_client.book_slot(...)`.
4. Успех → `mark_booked(...)` + уведомление пользователя.
5. `SlotNotFoundError` → статус возвращается в `WAITING` (ждём след. прогон).
6. `VFSBotError` → статус `ERROR` + уведомление.
7. Прочие исключения → статус `ERROR` (планировщик не падает).

Уведомления отправляются через callback `notifier`, который в `main.py`
создаётся фабрикой `make_notifier(bot)` и шлёт сообщение через `bot`.

---

## 9. Утилиты (`utils/`)

- **`config.py`** — `Settings` (pydantic-settings): `bot_token`,
  `database_url`, `vfs_base_url`, `vfs_login/password`,
  `check_interval_seconds` (≥30), `browser_headless`, `browser_timeout_ms`,
  `captcha_api_key`, `log_level`, `log_file`. `get_settings()` кэширован
  через `lru_cache` (singleton).
- **`logger.py`** — `setup_logger()`: вывод в stderr (цветной) и в файл с
  ротацией 10 МБ, хранением 14 дней и zip-сжатием. `diagnose=False` —
  значения переменных не логируются (защита персональных данных).
- **`validators.py`** — `parse_date` (формат `ДД.ММ.ГГГГ`, флаг `allow_past`),
  `parse_date_range`, `validate_email`, `validate_phone` (нормализация в
  E.164), `validate_latin_name`, `validate_passport`. Все при ошибке бросают
  `ValidationError`/`DateRangeError`.
- **`exceptions.py`** — иерархия от `VFSBotError`: `ValidationError`
  (→ `DateRangeError`), `BrowserError`, `VFSClientError`
  (→ `SlotNotFoundError`, `BookingError`, `SessionExpiredError`),
  `CaptchaError`, `DatabaseError` (→ `ApplicationNotFoundError`).

---

## 10. Тесты (`tests/`)

- `conftest.py` — подставляет фиктивные `BOT_TOKEN`/`DATABASE_URL`, чтобы
  тесты не требовали реального `.env`.
- `test_validators.py` — ~16 тестов всех валидаторов (даты, диапазоны,
  email, телефон, имя, паспорт).
- `test_client.py` — структуры `AvailableSlot`/`BookingResult`, поведение
  стаба капчи, формирование словаря заявителя.

Тесты не требуют реальных бота, БД или браузера. Запуск: `pytest`
(`asyncio_mode = "auto"`).

---

## 11. Конфигурация и запуск

Переменные окружения — в `.env` (см. `.env.example`): `BOT_TOKEN`,
`DATABASE_URL`, `VFS_BASE_URL`, `VFS_LOGIN/PASSWORD`,
`CHECK_INTERVAL_SECONDS`, `BROWSER_HEADLESS`, `BROWSER_TIMEOUT_MS`,
`CAPTCHA_API_KEY`, `LOG_LEVEL`, `LOG_FILE`.

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env          # заполнить BOT_TOKEN, DATABASE_URL и пр.
python main.py                # таблицы создаются автоматически
pytest                        # юнит-тесты
```

---

## 12. Что осталось реализовать (приоритеты)

1. **Браузерный клиент VFS** (`browser/client.py`) — главная задача: реальные
   `_open_booking_page`, `_scan_calendar`, `_select_slot`,
   `_fill_applicant_form`, `_confirm_booking` под конкретный центр/страну.
2. **Селекторы** (`browser/selectors.py`) — актуальные CSS/XPath через DevTools.
3. **Решатель капчи** (`browser/captcha_solver.py`) — при необходимости
   реальная реализация поверх внешнего сервиса; выбор в `get_captcha_solver`.
4. **Сохранение сессии** — задействовать модель `Session` и
   `BrowserManager.new_context(storage_state=...)`, чтобы не авторизоваться
   каждый раз.
5. **Инфраструктура (по желанию):** Alembic-миграции вместо `create_all`;
   Dockerfile + docker-compose (бот + PostgreSQL); шифрование чувствительных
   полей заявки в БД; возможность прервать FSM-диалог `/add` на любом шаге.

---

## 13. Важное предупреждение

Автоматизация записи и обход капчи могут нарушать Условия использования VFS
Global и применимое законодательство. Перед реальным запуском это необходимо
проверить. Бизнес-логика бота, БД и FSM — нейтральная инфраструктура; вся
специфика VFS изолирована в каталоге `browser/`.
