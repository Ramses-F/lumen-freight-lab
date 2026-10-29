#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== Lumen Freight Lab — démarrage ==="
docker compose build
docker compose up -d

echo
echo "En attente que les services soient prêts..."
for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:5000/healthz >/dev/null 2>&1; then
    echo "Helpdesk prêt."
    break
  fi
  sleep 1
done

echo
echo "Lab démarré. Portail apprenant : http://127.0.0.1:5000"
echo "Le service interne 'vault' n'est volontairement PAS exposé à l'hôte."
echo "Pour arrêter : scripts/stop.sh   |   Pour réinitialiser : scripts/reset.sh"
