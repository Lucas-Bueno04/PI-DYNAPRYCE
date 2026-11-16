#!/bin/sh
# Entrada única da imagem: api, worker ou cli (ADR-001).
set -eu
case "${1:-api}" in
  api) exec uvicorn --factory dynaprice.principal:criar_api --host 0.0.0.0 --port 8000 \
    --no-access-log --forwarded-allow-ips "${DYNAPRICE_PROXY_CONFIAVEL:-127.0.0.1}" ;;
  worker) exec dynaprice worker ;;
  cli) shift; exec dynaprice "$@" ;;
  *) echo "uso: api | worker | cli <comando>" >&2; exit 64 ;;
esac
