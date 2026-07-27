FROM python:3.13-slim

WORKDIR /app
COPY backend /app/backend
COPY alembic.ini /app/alembic.ini
RUN pip install --no-cache-dir /app/backend

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000"]

