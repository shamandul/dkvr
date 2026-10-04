#!/bin/sh
set -eu

TEMPLATE="/opt/drupal-settings/settings.php"
HTACCESS_TEMPLATE="/opt/drupal-settings/files.htaccess"
DOCROOT_FILE="/etc/drupal-docroot"
SALT_PLACEHOLDER="__DRUPAL_HASH_SALT__"

log() {
  echo "[entrypoint-drupal] $*" >&2
}

if [ -f "${DOCROOT_FILE}" ]; then
  DOCROOT="$(cat "${DOCROOT_FILE}")"
else
  DOCROOT="/var/www/html"
fi

SITES_DEFAULT="${DOCROOT}/sites/default"
TARGET="${SITES_DEFAULT}/settings.php"
MODE="${DRUPAL_SETTINGS_MODE:-auto}"

effective_mode() {
  case "$1" in
    auto|force|skip) printf '%s' "$1" ;;
    *)
      log "AVISO: DRUPAL_SETTINGS_MODE='$1' no valido (auto|force|skip); se usa 'auto'"
      printf 'auto'
      ;;
  esac
}

salt_from_settings() {
  # Ultimo $settings['hash_salt'] = '...'; del fichero (el instalador de
  # Drupal lo reescribe). Se ignora el marcador sin sustituir.
  salt="$(sed -n "s/.*\\\$settings\['hash_salt'\] = '\([^']*\)';.*/\1/p" "$1" 2>/dev/null | tail -1 || true)"
  if [ -n "${salt}" ] && [ "${salt}" != "${SALT_PLACEHOLDER}" ]; then
    printf '%s' "${salt}"
  fi
}

resolve_salt() {
  # 1) DRUPAL_HASH_SALT  2) settings.php existente  3) .hash_salt  4) nuevo
  if [ -n "${DRUPAL_HASH_SALT:-}" ]; then
    printf '%s' "${DRUPAL_HASH_SALT}"
    return 0
  fi
  salt=""
  if [ -f "${TARGET}" ]; then
    salt="$(salt_from_settings "${TARGET}")"
  fi
  if [ -z "${salt}" ] && [ -f "${SITES_DEFAULT}/.hash_salt" ]; then
    salt="$(tr -d '[:space:]' < "${SITES_DEFAULT}/.hash_salt")"
  fi
  if [ -z "${salt}" ]; then
    salt="$(php -r 'echo bin2hex(random_bytes(32));')"
    printf '%s' "${salt}" > "${SITES_DEFAULT}/.hash_salt"
    chown www-data:www-data "${SITES_DEFAULT}/.hash_salt" 2>/dev/null || true
    log "hash salt generado y guardado en ${SITES_DEFAULT}/.hash_salt"
  fi
  printf '%s' "${salt}"
}

ensure_dirs() {
  # Directorios que Drupal exige y que el modo force regenera en cada arranque.
  mkdir -p "${SITES_DEFAULT}/files"
  sync_dir="${DRUPAL_CONFIG_SYNC_DIR:-}"
  case "${sync_dir}" in
    "") sync_dir="${SITES_DEFAULT}/files/config/sync" ;;
    /*) ;;
    *) sync_dir="${DOCROOT}/${sync_dir}" ;;
  esac
  mkdir -p "${sync_dir}"
  # Proteccion de files/ (necesaria cuando el directorio viene de un volumen
  # o PVC vacio; el instalador solo la escribe al crear el sitio).
  if [ ! -f "${SITES_DEFAULT}/files/.htaccess" ] && [ -f "${HTACCESS_TEMPLATE}" ]; then
    cp "${HTACCESS_TEMPLATE}" "${SITES_DEFAULT}/files/.htaccess"
    log "proteccion .htaccess creada en ${SITES_DEFAULT}/files"
  fi
  chown -R www-data:www-data "${SITES_DEFAULT}/files" 2>/dev/null || true
  log "directorios listos: ${SITES_DEFAULT}/files y ${sync_dir}"
}

install_settings() {
  if [ ! -f "${TEMPLATE}" ]; then
    log "AVISO: no existe la plantilla ${TEMPLATE}; no se puede generar settings.php"
    return 0
  fi
  mkdir -p "${SITES_DEFAULT}"
  salt="$(resolve_salt)"
  SALT="${salt}" php -r '
    $tpl = file_get_contents($argv[1]);
    $out = str_replace("__DRUPAL_HASH_SALT__", getenv("SALT"), $tpl);
    if (file_put_contents($argv[2], $out) === FALSE) { exit(1); }
  ' "${TEMPLATE}" "${TARGET}"
  chown www-data:www-data "${TARGET}" 2>/dev/null || true
  log "settings.php generado desde la plantilla (${TARGET})"
}

MODE="$(effective_mode "${MODE}")"

ensure_dirs

case "${MODE}" in
  skip)
    log "DRUPAL_SETTINGS_MODE=skip: settings.php no se modifica"
    ;;
  force)
    install_settings
    ;;
  auto)
    if [ -f "${TARGET}" ]; then
      log "DRUPAL_SETTINGS_MODE=auto: settings.php existente (del repositorio), se respeta"
    else
      install_settings
    fi
    ;;
esac

if [ -x /usr/local/bin/docker-entrypoint.sh ]; then
  exec /usr/local/bin/docker-entrypoint.sh "$@"
fi
exec "$@"
