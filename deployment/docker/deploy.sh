#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")"
mkdir -p backups; chmod 700 backups
exec 9>.deploy.lock; flock -n 9 || { echo "another deployment is running" >&2; exit 1; }
compose() { docker compose --env-file .env -f compose.yml "$@"; }
healthy() { local deadline=$((SECONDS+180)); while ((SECONDS<deadline)); do [ "$(docker inspect --format "{{.State.Health.Status}}" ucm 2>/dev/null || true)" = healthy ] && return 0; sleep 3; done; return 1; }
preflight() {
  [ "$(uname -s)" = Linux ] || { echo "Linux is required"; exit 1; }
  command -v docker >/dev/null && docker compose version >/dev/null && command -v openssl >/dev/null && command -v tar >/dev/null
  [ -f compose.yml ] || { echo "compose.yml missing"; exit 1; }
  if [ ! -f .env ]; then cp .env.example .env; sed -i "s/UCM_SECRET_KEY=CHANGE_ME/UCM_SECRET_KEY=$(openssl rand -hex 32)/;s/UCM_JWT_SECRET=CHANGE_ME/UCM_JWT_SECRET=$(openssl rand -hex 32)/" .env; chmod 600 .env; echo "Set UCM_FQDN in .env, then rerun."; exit 1; fi
  grep -q "^UCM_FQDN=ucm.example.cz$" .env && { echo "Set UCM_FQDN in .env"; exit 1; }
  grep -q "=CHANGE_ME$" .env && { echo "Replace CHANGE_ME in .env"; exit 1; }
  compose config --quiet
}
backup() {
  local was=0 stamp dir tag digest; stamp=$(date -u +%Y%m%d-%H%M%S); dir="backups/$stamp"; mkdir -p "$dir"
  [ "$(docker inspect --format "{{.State.Running}}" ucm 2>/dev/null || true)" = true ] && was=1
  [ "$was" = 1 ] && compose stop
  tag=$(sed -n "s/^UCM_IMAGE_TAG=//p" .env); digest=$(docker image inspect --format "{{index .RepoDigests 0}}" "ghcr.io/norman67cz/ultimate-ca-manager-active24:$tag" 2>/dev/null || true)
  docker run --rm -v ucm-data:/v -v "$PWD/$dir":/b alpine tar czf /b/ucm-data.tar.gz -C /v .
  docker run --rm -v ucm-hsm-tokens:/v -v "$PWD/$dir":/b alpine tar czf /b/ucm-hsm-tokens.tar.gz -C /v .
  printf "BACKUP_AT=%s\nIMAGE_TAG=%s\nIMAGE_DIGEST=%s\n" "$(date -u +%FT%TZ)" "$tag" "$digest" > "$dir/metadata.env"; chmod 600 "$dir"/*
  [ "$was" = 1 ] && compose up -d && healthy; printf "%s\n" "$dir"
}
case "${1:-}" in
 install) preflight; compose pull; compose up -d; healthy; echo "UCM is healthy" ;;
 backup) preflight; backup ;;
 update) preflight; [ -n "${2:-}" ] || { echo "image tag required"; exit 2; }; old=$(sed -n "s/^UCM_IMAGE_TAG=//p" .env); backup; sed -i "s/^UCM_IMAGE_TAG=.*/UCM_IMAGE_TAG=$2/" .env; if ! compose pull ucm || ! compose up -d || ! healthy; then sed -i "s/^UCM_IMAGE_TAG=.*/UCM_IMAGE_TAG=$old/" .env; compose up -d; healthy || true; exit 1; fi ;;
 rollback) preflight; [ "${2:-}" = --yes ] || { read -r -p "Rollback latest backup? [y/N] " answer; [ "$answer" = y ] || exit 0; }; dir=$(find backups -mindepth 1 -maxdepth 1 -type d | sort | tail -1); [ -n "$dir" ] || exit 1; . "$dir/metadata.env"; compose stop; docker run --rm -v ucm-data:/v -v "$PWD/$dir":/b alpine sh -c "rm -rf /v/* && tar xzf /b/ucm-data.tar.gz -C /v"; docker run --rm -v ucm-hsm-tokens:/v -v "$PWD/$dir":/b alpine sh -c "rm -rf /v/* && tar xzf /b/ucm-hsm-tokens.tar.gz -C /v"; sed -i "s/^UCM_IMAGE_TAG=.*/UCM_IMAGE_TAG=$IMAGE_TAG/" .env; compose up -d; healthy ;;
 status) preflight; compose ps ;;
 logs) preflight; compose logs -f --tail=200 ;;
 stop) preflight; compose stop ;;
 start) preflight; compose up -d; healthy ;;
 *) echo "Usage: $0 {install|update TAG|backup|rollback [--yes]|status|logs|stop|start}"; exit 2 ;;
esac
