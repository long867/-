#!/usr/bin/env bash
# Reproducible Docker validation/builds from Linux or Windows WSL.
set -Eeuo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
case "${1:-config}" in
  config)
    docker compose --env-file .env.example -f deploy/docker-compose.yml -f deploy/docker-compose.production.yml config --quiet
    bash -n deploy/release.sh
    ;;
  alerts)
    docker run --rm --memory=128m --entrypoint promtool -v "$repo_root/deploy:/rules:ro" -w /rules prom/prometheus:v3.2.1 check rules alerts.yml
    docker run --rm --memory=128m --entrypoint promtool -v "$repo_root/deploy:/rules:ro" -w /rules prom/prometheus:v3.2.1 test rules alert-tests.yml
    ;;
  build)
    for image in api worker frontend backup; do
      case "$image" in api) file=backend/Dockerfile ;; worker) file=pipeline/Dockerfile ;; frontend) file=frontend/Dockerfile ;; backup) file=deploy/backup/Dockerfile ;; esac
      docker build -t "miningintel-$image:phase6" -f "$file" .
    done
    ;;
  *) echo 'Use config, alerts or build' >&2; exit 2 ;;
esac
