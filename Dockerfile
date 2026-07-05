# ---- Stage 1: build the Angular + eUI frontend -----------------------------
FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npx ng build --configuration production

# ---- Stage 2: Python runtime ------------------------------------------------
FROM python:3.12-slim
WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY knowledge/ knowledge/
COPY --from=frontend /build/dist/frontend/browser frontend/dist/frontend/browser

ENV KNOWLEDGE_DIR=/app/knowledge \
    STATIC_DIR=/app/frontend/dist/frontend/browser \
    DATA_DIR=/app/data \
    PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["sh", "-c", "cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
