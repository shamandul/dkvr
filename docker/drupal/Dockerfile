# syntax=docker/dockerfile:1

FROM alpine:3.20 AS clone

ARG DRUPAL_GIT_URL
ARG DRUPAL_GIT_REF=main
# Pasa --build-arg CACHEBUST=$(date +%s) para forzar el reclone de un commit
# nuevo (sin invalidar las capas de apt/pecl, que van antes del COPY).
ARG CACHEBUST=0

RUN apk add --no-cache git

RUN set -eu; \
    echo "cache-bust: ${CACHEBUST}"; \
    if [ -z "${DRUPAL_GIT_URL:-}" ]; then \
      echo "ERROR: falta el build arg DRUPAL_GIT_URL." >&2; \
      echo "Usa --build-arg DRUPAL_GIT_URL=https://github.com/usuario/repo.git" >&2; \
      exit 1; \
    fi; \
    git clone --depth 1 --branch "${DRUPAL_GIT_REF}" "${DRUPAL_GIT_URL}" /src

RUN set -eux; \
    if [ -f /src/index.php ]; then \
      REL=""; \
    elif [ -f /src/web/index.php ]; then \
      REL="web"; \
    elif [ -f /src/docroot/index.php ]; then \
      REL="docroot"; \
    else \
      echo "ERROR: no se encontro index.php (raiz, web/ ni docroot/) en el repositorio." >&2; \
      exit 1; \
    fi; \
    mkdir -p /out; \
    cp -a /src /out/repo; \
    printf '%s' "${REL}" > /out/docroot_rel; \
    echo "Docroot detectado: /var/www/html${REL:+/${REL}}"

FROM drupal:11-apache

COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer

RUN apt-get update \
    && apt-get install -y --no-install-recommends librdkafka-dev libzip-dev unzip git curl \
    && pecl install -n redis rdkafka \
    && docker-php-ext-enable redis rdkafka \
    && docker-php-ext-install zip \
    && rm -rf /var/lib/apt/lists/*

COPY settings.php /opt/drupal-settings/settings.php
COPY files.htaccess /opt/drupal-settings/files.htaccess
COPY entrypoint-drupal.sh /usr/local/bin/entrypoint-drupal.sh

COPY --from=clone /out/ /tmp/out/

RUN --mount=type=cache,target=/tmp/composer-cache \
    set -eux; \
    REL="$(cat /tmp/out/docroot_rel)"; \
    ROOT="/var/www/html"; \
    if [ -n "${REL}" ]; then ROOT="/var/www/html/${REL}"; fi; \
    rm -rf /var/www/html; \
    mkdir -p /var/www/html; \
    cp -a /tmp/out/repo/. /var/www/html/; \
    rm -rf /tmp/out; \
    if [ ! -f /var/www/html/vendor/autoload.php ] && [ -f /var/www/html/composer.json ]; then \
      echo "vendor/ ausente: ejecutando composer install"; \
      COMPOSER_ALLOW_SUPERUSER=1 COMPOSER_CACHE_DIR=/tmp/composer-cache \
        composer install --working-dir=/var/www/html --no-dev --no-interaction --no-progress --prefer-dist; \
      test -f /var/www/html/vendor/autoload.php; \
    fi; \
    git config --system --add safe.directory /var/www/html; \
    if [ ! -f /var/www/html/vendor/bin/drush ]; then \
      echo "Instalando drush/drush en el proyecto"; \
      COMPOSER_ALLOW_SUPERUSER=1 COMPOSER_CACHE_DIR=/tmp/composer-cache \
        composer require --working-dir=/var/www/html --no-interaction --no-progress --no-scripts drush/drush; \
      test -f /var/www/html/vendor/bin/drush; \
    fi; \
    ln -sf /var/www/html/vendor/bin/drush /usr/local/bin/drush; \
    mkdir -p "${ROOT}/sites/default/files"; \
    printf '%s' "${ROOT}" > /etc/drupal-docroot; \
    printf '<Directory "%s">\n\tOptions Indexes FollowSymLinks\n\tAllowOverride All\n\tRequire all granted\n</Directory>\n' "${ROOT}" \
      > /etc/apache2/conf-available/drupal-docroot.conf; \
    a2enconf drupal-docroot >/dev/null; \
    if [ -n "${REL}" ]; then \
      sed -ri "s#^([[:space:]]*)DocumentRoot[[:space:]]+/var/www/html[[:space:]]*\$#\1DocumentRoot ${ROOT}#" \
        /etc/apache2/sites-available/000-default.conf; \
      grep -q "DocumentRoot ${ROOT}" /etc/apache2/sites-available/000-default.conf; \
    fi; \
    chmod +x /usr/local/bin/entrypoint-drupal.sh; \
    chown -R www-data:www-data /var/www/html

ENTRYPOINT ["/usr/local/bin/entrypoint-drupal.sh"]
CMD ["apache2-foreground"]
