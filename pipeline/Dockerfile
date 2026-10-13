FROM python:3.12-slim
ARG INSTALL_ML=false
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/workspace:/workspace/backend PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
WORKDIR /workspace/backend
COPY backend/pyproject.toml backend/requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
RUN playwright install --with-deps chromium
COPY backend/app ./app
RUN pip install --no-cache-dir --no-deps .
RUN if [ "$INSTALL_ML" = "true" ]; then pip install --no-cache-dir '.[ml]'; fi
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./
COPY pipeline /workspace/pipeline
RUN useradd --create-home --uid 10001 appuser && mkdir -p /home/appuser/.cache /var/log/miningintel /var/lib/miningintel/beat && chown -R appuser:appuser /home/appuser/.cache /var/log/miningintel /var/lib/miningintel
USER appuser
CMD ["celery", "-A", "app.tasks.celery_app:celery_app", "worker", "--loglevel=INFO", "--queues=celery,nlp", "--concurrency=2"]
