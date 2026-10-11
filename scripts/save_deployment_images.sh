#!/usr/bin/env bash
# Export reviewed application and infrastructure images without credentials.
set -Eeuo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
output="$repo_root/artifacts/miningintel-phase6-images.tar.gz"
images=(miningintel-api:phase6 miningintel-worker:phase6
  miningintel-frontend:phase6 miningintel-backup:phase6
  pgvector/pgvector:pg16 redis:7-alpine qdrant/qdrant:v1.19.2
  nginx:1.28-alpine prom/prometheus:v3.2.1 grafana/grafana:11.6.0
  prom/alertmanager:v0.28.1)
docker save "${images[@]}" | gzip -3 > "$output.part"
gzip -t "$output.part"
mv -- "$output.part" "$output"
sha256sum "$output" > "$output.sha256"
du -h "$output"
