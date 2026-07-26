#!/bin/sh

set -eu

script_dir=$(
  CDPATH= cd -- "$(dirname -- "$0")"
  pwd -P
)
repository_root=$(dirname -- "$script_dir")

if ! command -v docker >/dev/null 2>&1; then
  echo "error: docker is not installed or is not available in PATH" >&2
  exit 127
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "error: the Docker Compose plugin is not available" >&2
  exit 1
fi

if [ ! -f "$repository_root/docker-compose.yml" ]; then
  echo "error: docker-compose.yml was not found at $repository_root" >&2
  exit 1
fi

echo "Building the frontend image..."
docker compose \
  --file "$repository_root/docker-compose.yml" \
  --project-directory "$repository_root" \
  build nginx

echo "Updating the running frontend container..."
docker compose \
  --file "$repository_root/docker-compose.yml" \
  --project-directory "$repository_root" \
  up \
  --detach \
  --no-deps \
  --force-recreate \
  nginx

echo "Frontend updated successfully."
