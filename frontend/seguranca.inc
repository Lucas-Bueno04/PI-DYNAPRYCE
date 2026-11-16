# Cabeçalhos de segurança da borda (F1.37). Incluído no server e em todo location que
# tenha add_header próprio, porque no nginx um add_header no location descarta os herdados.
# O CSS do Mantine usa estilos em linha; script só da própria origem.
add_header Content-Security-Policy "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "no-referrer" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
