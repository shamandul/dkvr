<?php

/**
 * @file
 * Configuracion generada por la imagen Docker (docker/drupal).
 *
 * Controlada por DRUPAL_SETTINGS_MODE (auto|force|skip) en el entrypoint.
 * Toda la configuracion se lee de variables de entorno en tiempo de
 * arranque, por lo que no se guardan secretos en el repositorio.
 *
 * Nota: el instalador de Drupal reescribe este fichero mediante
 * SettingsEditor::rewrite(), que solo admite asignaciones de un solo nivel
 * con valor escalar. Por eso no se anidan indices en $databases/$settings.
 */

// ---------------------------------------------------------------------------
// Base de datos (PostgreSQL).
// Si se omite 'namespace', el propio Drupal resuelve el namespace y el
// autoload del driver core 'pgsql' (Drupal >= 10.2). Para un driver de
// contrib define DB_DRIVER=postgresql y DB_NAMESPACE.
// ---------------------------------------------------------------------------
$database = [
  'driver' => getenv('DB_DRIVER') ?: 'pgsql',
  'host' => getenv('DB_HOST') ?: 'postgres',
  'port' => getenv('DB_PORT') ?: '5432',
  'database' => getenv('DB_NAME') ?: 'drupal',
  'username' => getenv('DB_USER') ?: 'drupal',
  'password' => getenv('DB_PASSWORD') ?: '',
  'pdo' => [
    PDO::ATTR_TIMEOUT => 10,
  ],
];

$db_namespace = getenv('DB_NAMESPACE');
if ($db_namespace) {
  $database['namespace'] = $db_namespace;
}

$databases['default']['default'] = $database;

// ---------------------------------------------------------------------------
// Hash salt: inyectado por el entrypoint (DRUPAL_HASH_SALT o valor persistido
// en sites/default/.hash_salt). El instalador lo sustituye in situ.
// ---------------------------------------------------------------------------
$settings['hash_salt'] = '__DRUPAL_HASH_SALT__';

// ---------------------------------------------------------------------------
// Hosts de confianza: DRUPAL_TRUSTED_HOSTS (separados por coma).
// Admite '*' como comodin (drupal.local,*.example.com).
// ---------------------------------------------------------------------------
$trusted_raw = getenv('DRUPAL_TRUSTED_HOSTS');
if ($trusted_raw === FALSE || $trusted_raw === '') {
  $trusted_raw = 'drupal.local,localhost,127.0.0.1';
}
$trusted_patterns = [];
foreach (explode(',', $trusted_raw) as $trusted_host) {
  $trusted_host = trim($trusted_host);
  if ($trusted_host === '') {
    continue;
  }
  $trusted_patterns[] = str_replace('\*', '.*', preg_quote($trusted_host, '/'));
}
$settings['trusted_host_patterns'] = $trusted_patterns;

// ---------------------------------------------------------------------------
// Detras de Varnish / Ingress: confiar en X-Forwarded-*.
// ---------------------------------------------------------------------------
$settings['reverse_proxy'] = TRUE;
$settings['reverse_proxy_addresses'] = [
  $_SERVER['REMOTE_ADDR'] ?? '127.0.0.1',
];
$settings['reverse_proxy_headers'] = [
  'HTTP_X_FORWARDED_FOR',
  'HTTP_X_FORWARDED_HOST',
  'HTTP_X_FORWARDED_PROTO',
  'HTTP_X_FORWARDED_PORT',
];

// ---------------------------------------------------------------------------
// Redis (solo si la extension php y el modulo de Drupal estan disponibles).
// ---------------------------------------------------------------------------
$redis_host = getenv('REDIS_HOST');
if ($redis_host && class_exists('Redis')) {
  $settings['redis.connection'] = [
    'interface' => 'PhpRedis',
    'host' => $redis_host,
    'port' => (int) (getenv('REDIS_PORT') ?: 6379),
  ];
  if (class_exists('Drupal\\redis\\Cache\\CacheBackendFactory')) {
    $settings['cache']['default'] = 'cache.backend.redis';
    $settings['cache']['bins']['discovery'] = 'cache.backend.chainedfast';
  }
}

// ---------------------------------------------------------------------------
// Directorio de sincronizacion de configuracion. Obligatorio: Drupal marca
// un error de requisitos si no esta definido o el directorio no existe.
// ---------------------------------------------------------------------------
$config_sync = getenv('DRUPAL_CONFIG_SYNC_DIR');
if (!$config_sync) {
  $sync_root = isset($app_root) ? $app_root : (defined('DRUPAL_ROOT') ? DRUPAL_ROOT : getcwd());
  $sync_site = isset($site_path) ? $site_path : 'sites/default';
  $config_sync = $sync_root . '/' . $sync_site . '/files/config/sync';
}
$settings['config_sync_directory'] = $config_sync;

// ---------------------------------------------------------------------------
// Ficheros privados (opcional).
// ---------------------------------------------------------------------------
$private_path = getenv('DRUPAL_FILE_PRIVATE_PATH');
if ($private_path) {
  $settings['file_private_path'] = $private_path;
}
