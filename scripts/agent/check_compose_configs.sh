#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

cd "$ROOT_DIR"

# 세 배포 진입점이 모두 병합 가능한 Compose 구성인지 확인합니다.
docker compose -f docker-compose.dev.yml config >/tmp/tailwind-dev-compose-config.yml
docker compose -f docker-compose.oidc.yml config >/tmp/tailwind-oidc-compose-config.yml
docker compose config >/tmp/tailwind-prod-compose-config.yml

echo "compose config passed: dev, oidc, prod"
