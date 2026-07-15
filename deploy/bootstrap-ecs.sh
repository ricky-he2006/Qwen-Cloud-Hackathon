#!/usr/bin/env bash
# Bootstrap Docker on Alibaba Cloud ECS (Ubuntu 22.04/24.04)
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo bash deploy/bootstrap-ecs.sh"
  exit 1
fi

apt-get update
apt-get install -y ca-certificates curl git

if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi

if ! docker compose version >/dev/null 2>&1; then
  apt-get install -y docker-compose-plugin || true
fi

systemctl enable docker
systemctl start docker

echo "Docker ready: $(docker --version)"
echo "Compose ready: $(docker compose version)"
