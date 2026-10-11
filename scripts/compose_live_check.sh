#!/usr/bin/env bash
# Start a separately named stack; never remove another project's volumes.
set -Eeuo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root/artifacts/compose-check"
compose=(docker compose --project-name miningintel-phase6-check --env-file .env -f deploy/docker-compose.yml -f deploy/check.yml --profile monitoring --profile backup)
case "${1:-start}" in
  start)
    "${compose[@]}" up -d --no-build --wait --wait-timeout 180
    "${compose[@]}" cp evidence-snapshot.json api:/tmp/evidence-snapshot.json
    "${compose[@]}" exec -T api python -m pipeline.transfer_data import /tmp/evidence-snapshot.json
    "${compose[@]}" exec -T api python -m pipeline.transfer_data import /tmp/evidence-snapshot.json
    "${compose[@]}" ps --format json
    ;;
  status) "${compose[@]}" ps ;;
  stop) "${compose[@]}" stop ;;
  *) echo 'Use start, status or stop' >&2; exit 2 ;;
esac
