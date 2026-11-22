#!/bin/sh
# Primeira carga do banco: cria papéis e banco; o esquema vem das migrações (F1.9).
set -eu
migrador="$(cat /run/secrets/pg_migrador)"
app="$(cat /run/secrets/pg_app)"
psql -v ON_ERROR_STOP=1 -U postgres -v migrador="$migrador" -v app="$app" \
  -f /docker-entrypoint-initdb.d/papeis.sql.in
