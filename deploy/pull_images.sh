#!/usr/bin/env bash
# Pull immutable layers directly; registry credentials exist only for this command.
set -Eeuo pipefail
set +x
umask 077
registry_owner="${1:?Pass the lowercase registry owner}"
image_revision="${2:?Pass the full commit SHA}"
registry_user="${3:?Pass the GitHub actor}"
[[ "$registry_owner" =~ ^[a-z0-9_-]+$ ]] || exit 2
[[ "$image_revision" =~ ^[a-f0-9]{40}$ ]] || exit 2
[[ "$registry_user" =~ ^[a-zA-Z0-9_-]+$ ]] || exit 2
registry_config=$(mktemp -d /tmp/miningintel-registry-login.XXXXXXXX)
trap 'rm -rf -- "$registry_config"' EXIT
IFS= read -r registry_token
[[ -n "$registry_token" ]] || { echo 'Missing short-lived registry token' >&2; exit 2; }
printf '%s' "$registry_token" | docker --config "$registry_config" login ghcr.io --username "$registry_user" --password-stdin >/dev/null
unset registry_token
for image in api worker frontend backup; do
  docker --config "$registry_config" pull "ghcr.io/$registry_owner/miningintel-$image:$image_revision"
done
