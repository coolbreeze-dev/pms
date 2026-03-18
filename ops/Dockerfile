FROM node:22-alpine AS frontend-build
WORKDIR /app
COPY design-system/package.json design-system/package-lock.json* /app/design-system/
RUN cd /app/design-system && if [ -f package-lock.json ]; then npm ci; else npm install; fi
COPY design-system /app/design-system
RUN cd /app/design-system && npm run build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi
COPY frontend/ .
RUN npm run build

FROM python:3.12-slim AS backend
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /app
COPY backend /app/backend
COPY ops/start-app.sh /app/ops/start-app.sh
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --upgrade pip \
    && pip install /app/backend \
    && useradd --create-home --uid 10001 appuser \
    && mkdir -p /data /backups \
    && chmod +x /app/ops/start-app.sh \
    && chown -R appuser:appuser /app /data /backups
WORKDIR /app/backend
EXPOSE 8000
USER appuser
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import os, urllib.request; urllib.request.urlopen(f\"http://127.0.0.1:{os.environ.get('PORT', '8000')}/api/ready\").read()"
CMD ["/app/ops/start-app.sh"]
