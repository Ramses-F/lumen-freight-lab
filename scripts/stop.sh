#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== Lumen Freight Lab — arrêt ==="
docker compose down
echo "Services arrêtés (les données du helpdesk sont conservées dans le volume)."
