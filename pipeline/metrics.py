"""Bounded-label Prometheus collection metrics."""

from prometheus_client import Counter, Histogram

FETCHED = Counter("miningintel_collector_fetched", "Fetched candidates", ["source"])
INSERTED = Counter("miningintel_collector_inserted", "New articles", ["source"])
DUPLICATES = Counter(
    "miningintel_collector_duplicates", "Duplicate candidates", ["source"]
)
ERRORS = Counter("miningintel_collector_errors", "Pipeline errors", ["source", "stage"])
DURATION = Histogram(
    "miningintel_collector_duration_seconds", "Fetch/storage duration", ["source"]
)
FETCH_RUNS = Counter("miningintel_fetch_runs", "Collection runs", ["source", "outcome"])
TRANSLATIONS = Counter(
    "miningintel_translation_runs", "Translation attempts", ["outcome"]
)
TASKS = Counter("miningintel_task_runs", "Celery attempts", ["task", "state"])
TASK_DURATION = Histogram(
    "miningintel_task_duration_seconds", "Celery attempt time", ["task"]
)
