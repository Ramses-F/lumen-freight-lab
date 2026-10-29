#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== Lumen Freight Lab — réinitialisation complète ==="
docker compose down -v
docker compose build
docker compose up -d

echo "En attente que les services soient prêts..."
for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:5000/healthz >/dev/null 2>&1; then
    echo "Helpdesk prêt."
    break
  fi
  sleep 1
done

echo "Lab réinitialisé : base de données recréée, jeu de données ré-injecté."
echo "Portail apprenant : http://127.0.0.1:5000"
