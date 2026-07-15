#!/usr/bin/env bash
# Build and start Research Society on ECS
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  echo "Creating .env from .env.production.example — edit API_KEY before production use."
  cp .env.production.example .env
  echo "Edit $ROOT_DIR/.env then re-run: bash deploy/deploy.sh"
  exit 1
fi

if grep -q "sk-your-dashscope-api-key\|API_KEY=not-needed\|API_KEY=$" .env; then
  echo "ERROR: Set a real DashScope API_KEY in .env (pay-as-you-go sk-... key)"
  exit 1
fi

if grep -qE '^API_KEY=sk-sp-' .env || grep -qE '^DASHSCOPE_API_KEY=sk-sp-' .env; then
  echo "ERROR: Token Plan keys (sk-sp-...) cannot be used for this backend."
  echo "Create a pay-as-you-go key (sk-...) at https://home.qwencloud.com/api-keys"
  exit 1
fi

if ! grep -qE '^API_KEY=sk-' .env && ! grep -qE '^DASHSCOPE_API_KEY=sk-' .env; then
  echo "ERROR: .env must contain API_KEY=sk-... (or DASHSCOPE_API_KEY=sk-...)"
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

# Avoid host port clash when nginx profile is used
if [[ "${COMPOSE_PROFILES:-}" == *nginx* ]] || [[ "$*" == *nginx* ]]; then
  export APP_PORT="${APP_PORT:-8000}"
fi

docker compose build --pull
docker compose up -d

echo ""
echo "Waiting for health check on port ${APP_PORT:-80}..."
for i in {1..30}; do
  if curl -fsS "http://127.0.0.1:${APP_PORT:-80}/api/health" >/dev/null 2>&1; then
    echo "OK — Research Society is live on port ${APP_PORT:-80}"
    curl -s "http://127.0.0.1:${APP_PORT:-80}/api/health"
    echo ""
    exit 0
  fi
  sleep 2
done

echo "Service did not become healthy in time. Logs:"
docker compose logs --tail=80
exit 1
