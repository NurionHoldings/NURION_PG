ARG BASE_IMAGE
FROM ${BASE_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 NURION_PG_ENV=production
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY scripts/migrate_ops_database.py ./scripts/migrate_ops_database.py
RUN pip install --no-cache-dir --no-compile . && rm -rf /root/.cache
USER 65532:65532
EXPOSE 8080
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health/live', timeout=2)"]
CMD ["nurion-pg-api"]
