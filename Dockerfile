# syntax=docker/dockerfile:1.7
FROM node:24-alpine AS frontend
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run test && npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /app
RUN addgroup --system insightpulse && adduser --system --ingroup insightpulse insightpulse
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
RUN pip install --no-cache-dir .
COPY --from=frontend /build/frontend/dist ./frontend/dist
RUN mkdir -p /app/artifacts && chown -R insightpulse:insightpulse /app
USER insightpulse
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f\"http://127.0.0.1:{os.getenv('PORT','8000')}/ready\", timeout=2)"
CMD ["sh", "-c", "uvicorn insightpulse_api.app:create_app --factory --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
