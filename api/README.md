# api/ — Go-бэкенд (REST API + Telegram-бот)

Ядро на Go: REST API для фронтенда, аутентификация, БД (PostgreSQL), клиент к
Python-воркеру обхода. Бот на Go — уведомления и статусы.

```
api/
├── go.mod
├── cmd/
│   ├── server/main.go   # REST API + отдача фронта
│   └── bot/main.go      # Telegram-бот
└── internal/
    ├── config/          # настройки из окружения
    ├── store/           # PostgreSQL: пользователи, заявки
    ├── auth/            # bcrypt + cookie-сессии (HMAC)
    ├── worker/          # HTTP-клиент к Python-воркеру (WORKER_API.md)
    └── server/          # роутер и хендлеры API
```

## Зависимости и сборка
```bash
cd api
go mod tidy        # подтянет pgx, x/crypto, telebot
go build ./...
```

## Окружение (env)
```env
ADDR=:8000
DATABASE_URL=postgres://vfs_user:vfs_password@localhost:5432/vfs_bot?sslmode=disable
FRONTEND_DIR=../frontend
WORKER_URL=http://127.0.0.1:8800
WEBAPP_SECRET=длинная_случайная_строка
VFS_LOGIN=аккаунт_VFS@mail.ru
VFS_PASSWORD=пароль_VFS
BOT_TOKEN=токен_бота
```

## Запуск (3 процесса)
```bash
# 1. Python-воркер (обход) — из ../backend
cd ../backend && uvicorn worker_app:app --port 8800

# 2. Go API + сайт
cd ../api && go run ./cmd/server     # http://127.0.0.1:8000

# 3. Telegram-бот (опционально)
go run ./cmd/bot
```

## API (для фронта)
`GET /api/me` · `POST /api/register` · `POST /api/login` · `POST /api/logout` ·
`GET /api/options` · `GET /api/tasks` · `POST /api/tasks` · `GET /api/tasks/{id}` ·
`DELETE /api/tasks/{id}` · `POST /api/tasks/{id}/search`

Аутентификация — подписанная cookie-сессия (same-origin, фронт отдаёт этот же
сервер). Поиск слотов ставится в Python-воркер; фоновый опрос обновляет статус
заявки (`searching` → `booked`/`created`/`error`).

## Что дальше
- Привязка Telegram-аккаунта к пользователю + пуш-уведомления о слотах.
- Логин/пароль VFS пока берётся из env (один аккаунт). Для мультиаккаунта —
  хранить per-task (с шифрованием), как и карты.
- Перевод фронта на этот API вместо текущего FastAPI-сайта.
```
