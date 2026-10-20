FROM python:3.13-slim


# Установка зависимостей системы
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    pkg-config \
    postgresql-client \
  && rm -rf /var/lib/apt/lists/*

# Установка Poetry через pip
RUN pip install --no-cache-dir poetry

# Настройки Poetry
ENV POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1 \
    PYTHONUNBUFFERED=1

# Создание рабочей директории
WORKDIR /app

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 755 /usr/local/bin/entrypoint.sh \
    && sed -i 's/\r$//' /usr/local/bin/entrypoint.sh

# Копирование файлов Poetry
COPY pyproject.toml poetry.lock* /app/

# Установка зависимостей проекта
RUN poetry install --only main --no-root

# Копирование исходного кода
COPY . /app

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
