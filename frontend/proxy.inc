# M3: X-Forwarded-For é sobrescrito com o endereço que o proxy viu; a API só confia no IP do proxy.
proxy_set_header Host $host;
proxy_set_header X-Forwarded-For $remote_addr;
proxy_set_header X-Forwarded-Proto https;
proxy_read_timeout 120s;
