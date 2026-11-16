# Borda (F1.37): constrói a SPA e serve por nginx sem root, na mesma origem da API (ADR-001).
FROM node:24.22.2-slim AS construcao
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.30.6-alpine
COPY --from=construcao /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY proxy.inc /etc/nginx/conf.d/proxy.inc
COPY seguranca.inc /etc/nginx/conf.d/seguranca.inc
