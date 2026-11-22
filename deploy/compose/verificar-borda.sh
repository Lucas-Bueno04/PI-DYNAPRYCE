#!/bin/sh
# F1.37: confere a borda ao vivo contra o compose em pé (https://localhost:8443).
set -eu
U=${1:-https://localhost:8443}
falha=0
ok() { printf 'ok    %s\n' "$1"; }
ruim() { printf 'FALHA %s\n' "$1"; falha=1; }
H=$(curl -ksI "$U/")
for c in "content-security-policy: default-src 'self'" "strict-transport-security:" "x-content-type-options: nosniff" "referrer-policy:"; do
  printf '%s' "$H" | grep -qi "$c" && ok "cabeçalho $c" || ruim "cabeçalho $c"
done
printf '%s' "$H" | grep -qi '^server:.*[0-9]\.[0-9]' && ruim "versão do nginx exposta" || ok "versão do nginx oculta"
curl -ksI "$U/api/v1/saude" | grep -qi 'strict-transport-security' && ok "HSTS também na API" || ruim "HSTS na API"
[ "$(curl -ks -o /dev/null -w '%{http_code}' "$U/rota-spa-qualquer")" = 200 ] && ok "fallback da SPA" || ruim "fallback da SPA"
curl -ks --tlsv1.1 --tls-max 1.1 -o /dev/null "$U/" 2>/dev/null && ruim "TLS 1.1 aceito" || ok "TLS 1.1 recusado"
n429=0
for i in $(seq 1 60); do
  c=$(curl -ks -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' -d '{}' "$U/api/v1/auth/login")
  [ "$c" = 429 ] && n429=$((n429 + 1))
done
[ "$n429" -gt 0 ] && ok "limite de taxa no login ($n429 respostas 429)" || ruim "sem 429 no login"
c=$(head -c 2000000 /dev/zero | curl -ks -o /dev/null -w '%{http_code}' -X POST --data-binary @- "$U/api/v1/auth/x-corpo" 2>/dev/null || true)
[ "$c" = 413 ] && ok "corpo > 1 MB recusado (413)" || ruim "corpo grande retornou $c"
exit $falha
