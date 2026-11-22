#!/bin/sh
# Gera segredos DESCARTÁVEIS para o ambiente local. Nunca use estes valores no piloto.
set -eu
cd "$(dirname "$0")"
mkdir -p segredos
cd segredos
gera() { [ -f "$1" ] || { openssl rand -hex 24 > "$1"; }; }
gera pg_superusuario; gera pg_migrador; gera pg_app; gera chave_pseudonimo
printf 'postgresql://dynaprice_migrador:%s@pg:5432/dynaprice' "$(cat pg_migrador)" > db_url_migrador
printf 'postgresql://dynaprice_app:%s@pg:5432/dynaprice' "$(cat pg_app)" > db_url_app
[ -f chaves_mestras ] || printf '{"k1": "%s"}' "$(openssl rand -base64 32)" > chaves_mestras
if [ ! -f chave_es256 ]; then
  openssl ecparam -name prime256v1 -genkey -noout | openssl pkcs8 -topk8 -nocrypt -out es256.pem
  python3 -c 'import json;print(json.dumps({"kid":"k1","privada":open("es256.pem").read(),"publicas_anteriores":{}}))' > chave_es256
  rm es256.pem
fi
mkdir -p tls
[ -f tls/tls.crt ] || openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes \
  -keyout tls/tls.key -out tls/tls.crt -days 30 -subj "/CN=localhost" -addext "subjectAltName=DNS:localhost"
chmod 644 tls/tls.key  # o nginx sem root precisa ler; vale só para o certificado descartável
chmod 644 chave_es256 chaves_mestras chave_pseudonimo db_url_app db_url_migrador pg_* 
