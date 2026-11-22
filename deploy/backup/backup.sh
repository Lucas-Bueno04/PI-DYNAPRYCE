#!/bin/sh
# Backup lógico diário (F1.39). DESTINO deve apontar para fora do host do banco no piloto.
# O arquivamento de WAL fica em deploy/backup/README.md.
set -eu
: "${DESTINO:?defina DESTINO}"
: "${PGHOST:?defina PGHOST}"
arquivo="$DESTINO/dynaprice-$(date -u +%Y%m%dT%H%M%SZ).dump"
pg_dump -d dynaprice -Fc -f "$arquivo"
pg_restore --list "$arquivo" > /dev/null
echo "$arquivo"
