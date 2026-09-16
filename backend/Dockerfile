FROM node:22-alpine AS frontend-build

WORKDIR /source/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./

# An empty URL makes browser requests use this service's own origin.
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build


FROM python:3.13-slim

WORKDIR /app
COPY backend /app/backend
COPY alembic.ini /app/alembic.ini
COPY --from=frontend-build /source/frontend/dist /app/frontend/dist
RUN pip install --no-cache-dir /app/backend

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port ${PORT:-8000}"]
