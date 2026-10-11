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
base_compose=(docker compose --project-name miningintel --env-file .env -f deploy/docker-compose.yml -f deploy/docker-compose.production.yml)
deployment_mode=standard
if [[ -f .deploy-mode ]]; then
  deployment_mode=$(tr -d '\r\n' < .deploy-mode)
fi
case "$deployment_mode" in
  standard) ;;
  small)
    export COMPOSE_PROFILES=''
    base_compose+=(-f deploy/docker-compose.small.yml)
    ;;
  *) echo 'Invalid deployment mode; use standard or small' >&2; exit 2 ;;
esac
compose=("${base_compose[@]}" --env-file .images.next.env)
"${compose[@]}" config --quiet
if [[ "${MININGINTEL_IMAGES_PRELOADED:-false}" == true ]]; then
  while IFS= read -r image; do
    docker image inspect "$image" >/dev/null
  done < <("${compose[@]}" config --images)
else
  "${compose[@]}" pull
fi
if [[ -f .images.env ]]; then cp .images.env .images.previous.env; fi
if [[ "$deployment_mode" == small ]]; then
  # Stop this project's optional services only; keep their data volumes.
  "${compose[@]}" stop prometheus grafana alertmanager backup qdrant
fi
"${compose[@]}" run --rm migrate
"${compose[@]}" up -d --no-build --remove-orphans
healthy=false
stack_ready=false
# Beat's previous leader lease can take 90 seconds to expire after recreation.
if "${compose[@]}" up -d --no-build --wait --wait-timeout 300; then
  stack_ready=true
fi
for attempt in $(seq 1 12); do
  [[ "$stack_ready" == true ]] || break
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
    "${base_compose[@]}" --env-file .images.previous.env up -d --no-build
  fi
  exit 1
fi
