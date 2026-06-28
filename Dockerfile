# Образ бэкенда (FastAPI + движок). Контекст сборки — корень проекта.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Зависимости Python
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Браузер для автоматизации (нужен движку; для чистого сайта можно убрать).
RUN python -m playwright install --with-deps chromium

# Код проекта
COPY . .

# Бэкенд запускается из своей папки (там лежат webapp/, core/, vfs_site/ ...)
WORKDIR /app/backend

EXPOSE 8000
CMD ["uvicorn", "webapp.main:app", "--host", "0.0.0.0", "--port", "8000"]
