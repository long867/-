#!/usr/bin/env bash
# Deploy immutable images; retain previous image references on failed health checks.
set -Eeuo pipefail
umask 077
deployment_root="${1:?Pass the absolute deployment directory}"
case "$deployment_root" in /opt/*|/srv/*|/home/*) ;; *) echo 'Use a dedicated /opt, /srv or /home directory' >&2; exit 2 ;; esac
[[ "$deployment_root" =~ ^/[a-zA-Z0-9_/-]+$ && "$deployment_root" != */../* ]] || exit 2
cd "$deployment_root"
[[ -f .env && -f .images.next.env ]] || { echo 'Missing server .env or image references' >&2; exit 2; }
exec 9> .deploy.lock
flock -n 9 || { echo 'A deployment is already running' >&2; exit 3; }
compose=(docker compose --project-name miningintel --env-file .env --env-file .images.next.env -f deploy/docker-compose.yml -f deploy/docker-compose.production.yml)
"${compose[@]}" config --quiet
if [[ "${MININGINTEL_IMAGES_PRELOADED:-false}" == true ]]; then
  while IFS= read -r image; do
    docker image inspect "$image" >/dev/null
  done < <("${compose[@]}" config --images)
else
  "${compose[@]}" pull
fi
if [[ -f .images.env ]]; then cp .images.env .images.previous.env; fi
"${compose[@]}" run --rm migrate
"${compose[@]}" up -d --no-build --remove-orphans
healthy=false
for attempt in $(seq 1 30); do
  if "${compose[@]}" exec -T api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready', timeout=3)" >/dev/null 2>&1 && \
     "${compose[@]}" exec -T frontend node -e "fetch('http://127.0.0.1:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))" >/dev/null 2>&1; then
    healthy=true; break
  fi
  sleep 5
done
if [[ "$healthy" == true ]]; then
  mv .images.next.env .images.env
  echo 'MiningIntel release is healthy'
else
  echo 'Release health checks failed; restoring previous images' >&2
  if [[ -f .images.previous.env ]]; then
    docker compose --project-name miningintel --env-file .env --env-file .images.previous.env -f deploy/docker-compose.yml -f deploy/docker-compose.production.yml up -d --no-build
  fi
  exit 1
fi
