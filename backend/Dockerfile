FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/workspace:/workspace/backend
WORKDIR /workspace/backend
COPY backend/pyproject.toml backend/requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY backend/app ./app
RUN pip install --no-cache-dir --no-deps .
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./
COPY pipeline /workspace/pipeline
RUN useradd --create-home --uid 10001 appuser && mkdir -p /var/log/miningintel /var/lib/miningintel/beat && chown -R appuser:appuser /var/log/miningintel /var/lib/miningintel
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
