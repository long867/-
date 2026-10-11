FROM postgres:16-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/backup
COPY deploy/backup/requirements.txt ./
RUN python3 -m venv /opt/backup/venv && /opt/backup/venv/bin/pip install --no-cache-dir -r requirements.txt
COPY deploy/backup/backup.py ./
RUN useradd --uid 10001 --create-home miningbackup && mkdir -p /var/backups/miningintel && chown miningbackup:miningbackup /var/backups/miningintel
USER miningbackup
ENV PYTHONUNBUFFERED=1
CMD ["/opt/backup/venv/bin/python", "backup.py", "--daemon"]
