FROM node:22-alpine AS frontend
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

RUN groupadd --system atendimento && useradd --system --gid atendimento --home-dir /app atendimento
COPY pyproject.toml README.md ./
COPY app ./app
COPY --from=frontend /web/dist ./app/web
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
RUN python -m pip install --no-cache-dir . \
    && mkdir /data \
    && chown atendimento:atendimento /data

USER atendimento
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --no-access-log"]
