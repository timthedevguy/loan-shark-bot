# ---- Builder Stage ----
FROM python:3.12-alpine AS builder

WORKDIR /build

# gcc + musl-dev needed to compile native extensions (tortoise-orm[accel] pulls in ciso8601/uvloop)
RUN apk add --no-cache gcc musl-dev libffi-dev

COPY pyproject.toml poetry.lock ./

# Export pinned requirements then install into a prefix we can copy cleanly
RUN pip install --no-cache-dir "poetry>=2.0.0,<3.0.0" \
    && poetry export --without dev --without-hashes -f requirements.txt -o requirements.txt \
    && pip install --no-cache-dir --prefix=/deps -r requirements.txt


# ---- Final Stage ----
FROM python:3.12-alpine

WORKDIR /app

# Copy compiled packages from builder
COPY --from=builder /deps /usr/local

# Copy only the application source (no tests, no dev files)
COPY cogs/       ./cogs/
COPY database.py models.py utils.py start_shark.py ./

# Non-root user + persistent data directory for SQLite
RUN addgroup -S shark \
    && adduser -S shark -G shark \
    && mkdir -p /data \
    && chown shark:shark /data

USER shark

# Store the SQLite file on the mounted volume so it survives container restarts
ENV DATABASE_URL=sqlite:////data/db.sqlite3

VOLUME ["/data"]

CMD ["python", "start_shark.py"]
