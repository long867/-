#!/usr/bin/env bash
# Restore only to a newly created, separately named acceptance-test database.
set -Eeuo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
container=miningintel-phase6-check-postgres-1
scratch=miningintel_restore_phase6
dump="$repo_root/artifacts/phase6-verified.dump"
existing=$(docker exec "$container" psql -U miningintel -d miningintel -Atc "SELECT 1 FROM pg_database WHERE datname='$scratch'")
[[ -z "$existing" ]] || { echo 'Scratch database already exists; refusing to overwrite' >&2; exit 2; }
docker exec "$container" pg_dump -U miningintel -d miningintel --format=custom --no-owner --no-privileges > "$dump"
docker exec -i "$container" pg_restore --list < "$dump" > "$repo_root/artifacts/phase6-dump-list.txt"
docker exec "$container" createdb -U miningintel "$scratch"
trap 'docker exec "$container" dropdb -U miningintel "$scratch"' EXIT
docker exec -i "$container" pg_restore -U miningintel -d "$scratch" --no-owner --no-privileges --exit-on-error < "$dump"
expected=$(docker exec "$container" psql -U miningintel -d miningintel -Atc 'SELECT count(*) FROM articles')
actual=$(docker exec "$container" psql -U miningintel -d "$scratch" -Atc 'SELECT count(*) FROM articles')
[[ "$expected" == "$actual" && "$actual" -gt 0 ]]
printf 'Verified PostgreSQL 16 custom dump and scratch restore: %s articles\n' "$actual"
sha256sum "$dump"
