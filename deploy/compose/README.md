# Ambiente local (compose)

Os segredos ficam em `segredos/`, que o git ignora. Crie um arquivo por segredo antes de subir:

| Arquivo | Conteúdo |
|---|---|
| `pg_superusuario`, `pg_migrador`, `pg_app` | senhas do banco |
| `db_url_migrador` | `postgresql://dynaprice_migrador:<senha>@pg:5432/dynaprice` |
| `db_url_app` | `postgresql://dynaprice_app:<senha>@pg:5432/dynaprice` |
| `chaves_mestras` | JSON `{"k1": "<32 bytes em base64>"}`; a última é a de cifragem |
| `chave_pseudonimo` | texto aleatório com 16 ou mais caracteres; mudar invalida os pseudônimos já gravados |
| `chave_es256` | JSON `{"kid": "k1", "privada": "<PEM>", "publicas_anteriores": {}}` |

Para subir: `docker compose -f deploy/compose/compose.yaml up --build`.

## Local

1. `./gerar-segredos-dev.sh` cria segredos descartáveis e um certificado autoassinado em `segredos/`.
2. Imagens (nesta máquina o DNS dos contêineres só funciona com a rede do host): `docker build --network=host -t dynaprice-backend:dev ../../backend` e o mesmo para `-t dynaprice-web:dev ../../frontend`.
3. `docker compose up -d` e abrir `https://localhost:8443/` (o navegador pede para aceitar o certificado).
4. Primeiro administrador: `docker compose run --rm -e DYNAPRICE_SENHA_ADMIN=<senha> api cli criar-admin --inquilino "<escritório>" --email <e-mail>`.
5. Borda: com o compose em pé, `./verificar-borda.sh` confere cabeçalhos (CSP, HSTS), limite de taxa (429), corpo máximo (413), TLS ≥ 1.2 e o fallback da SPA.

Notas desta máquina (kernel 7.0): o Docker Hub devolve 429 com frequência; `docker pull mirror.gcr.io/library/<imagem>` e `docker tag` para o nome original contorna. `no-new-privileges` impede qualquer contêiner de executar aqui (até `postgres`); o compose mantém a proteção, e para testar localmente use um override com `security_opt: !reset []` fora do repositório. Em outro host, não precisa de override.
