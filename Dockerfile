FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

RUN mkdir /code
WORKDIR /code
COPY cogs/       ./cogs/
COPY database.py models.py utils.py start_shark.py poetry.lock pyproject.toml ./

RUN apt-get update -y \
    && apt-get install -y --no-install-recommends gcc musl-dev libffi-dev \
    && pip install --upgrade pip \
    && pip install --no-cache-dir poetry \
    && poetry config virtualenvs.create false \
    && poetry install --no-interaction --without dev

# Store the SQLite file on the mounted volume so it survives container restarts
ENV DATABASE_URL=sqlite:////data/db.sqlite3

VOLUME ["/data"]

CMD ["python", "start_shark.py"]