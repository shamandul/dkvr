vcl 4.1;

backend default {
    .host = "drupal";
    .port = "80";
    .connect_timeout = 5s;
    .first_byte_timeout = 60s;
}

sub vcl_recv {
    if (req.method != "GET" && req.method != "HEAD") {
        return (pass);
    }

    # Instalacion, actualizacion, cron, batch y administracion: sin cache.
    if (req.url ~ "^/(core/)?(install|update|cron|authorize|rebuild)\.php" ||
        req.url ~ "^/batch" ||
        req.url ~ "^/admin" ||
        req.url ~ "^/user" ||
        req.url ~ "^/node/add") {
        return (pass);
    }

    # Cualquier sesión de Drupal (SESS/SSESS/MESS) invalida el cache compartido.
    if (req.http.Cookie ~ "(^|;\s*)(SESS|SSESS|MESS)[0-9a-f]{10,}=") {
        return (pass);
    }

    # Cookies residuales (has_js, big_pipe, etc.) no afectan al contenido.
    unset req.http.Cookie;

    return (hash);
}

sub vcl_backend_response {
    # Nunca cachear redirecciones.
    if (beresp.status >= 300 && beresp.status < 400) {
        set beresp.uncacheable = true;
        return (deliver);
    }

    # Nunca cachear respuestas con cookies (sesion, mensajes, CSRF).
    if (beresp.http.Set-Cookie) {
        set beresp.uncacheable = true;
        return (deliver);
    }

    if (beresp.http.Vary == "*" ||
        beresp.http.Cache-Control ~ "(?i)no-store") {
        set beresp.uncacheable = true;
        return (deliver);
    }

    # Drupal marca como reutilizable lo que ya cacheo el (page cache / dynamic
    # page cache) o lo que declara publico; el resto se entrega sin cachear.
    if (beresp.status == 200 && (beresp.http.X-Drupal-Cache == "HIT" ||
        beresp.http.Cache-Control ~ "(?i)public")) {
        set beresp.ttl = 5m;
    }
    else {
        set beresp.uncacheable = true;
    }

    return (deliver);
}
