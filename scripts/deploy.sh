#!/bin/bash
# Deploy rapido CareerOS — copia il frontend sul server via tar-over-ssh.
# NON tocca git: i commit si fanno a parte, solo per le versioni stabili.
#
# Uso (da Git Bash, nella root del progetto):
#   bash scripts/deploy.sh            # solo frontend (caso normale)
#   bash scripts/deploy.sh --backend  # frontend + backend/app (poi riavvia uvicorn)
set -e

SERVER="rudy@192.168.188.123"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 1. Timestamp di deploy → frontend/src/version.ts (lo vede la pagina)
STAMP="$(date '+%Y-%m-%d %H:%M')"
cat > "$ROOT/frontend/src/version.ts" <<EOF
// Aggiornato automaticamente da scripts/deploy.sh ad ogni deploy. Non modificare a mano.
export const BUILD_TIME = '$STAMP'
EOF
echo "→ versione: $STAMP"

# 2. Sincronizza frontend/src (tar evita l'annidamento src/src di scp -r)
echo "→ copia frontend/src..."
tar -C "$ROOT/frontend/src" -cf - . | ssh "$SERVER" "tar -C ~/CareerOS/frontend/src -xf -"

# 3. Backend opzionale
if [ "$1" = "--backend" ]; then
  echo "→ copia backend/app..."
  tar -C "$ROOT/backend/app" -cf - . | ssh "$SERVER" "tar -C ~/CareerOS/backend/app -xf -"
  echo "→ riavvio servizi (run-careeros.sh)..."
  ssh "$SERVER" "nohup bash ~/run-careeros.sh >/tmp/careeros-restart.log 2>&1 &"
fi

echo "✓ deploy fatto. Vite HMR ricarica da solo → http://192.168.188.123:5173 (agg. $STAMP)"
