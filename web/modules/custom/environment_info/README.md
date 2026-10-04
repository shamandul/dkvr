# Módulo environment_info

Bloque que muestra el entorno, la versión (tag de git) y la rama actual del sitio.

## Variable de entorno

El entorno se resuelve en `src/BuildInfo.php` con este orden:

1. `APP_ENV` (variable estándar)
2. `ENVIRONMENT` (alternativa)
3. `unknown` si ninguna está definida

Valores soportados: `dev`, `int`, `pre`, `pro`.

> **Importante:** `IS_DDEV_PROJECT` no es un selector de entorno. Lo inyecta
> automáticamente DDEV en los ficheros `.ddev/.ddev-docker-compose-*.yaml`
> (auto-generados, no editar) y solo se usa en `settings.php` para cargar
> `settings.ddev.php`.

## Dónde configurar APP_ENV

| Entorno | Dónde se configura |
|---------|--------------------|
| `dev`   | `.ddev/config.yaml` → `web_environment: [APP_ENV=dev]` (requiere `ddev restart`) |
| `int`   | Variable de entorno del despliegue (aún no definido) |
| `pre`   | Variable de entorno del despliegue (aún no definido) |
| `pro`   | Variable de entorno del despliegue (aún no definido) |

Cuando exista el despliegue de int/pre/pro, `APP_ENV` debe inyectarse en el
contenedor o servidor:

- Docker Compose: `environment: [APP_ENV=int]` en el servicio web.
- Kubernetes: `env: [{name: APP_ENV, value: "int"}]` en el Pod/Deployment.
- CI/CD: variable de entorno del job de despliegue.
- PHP-FPM: si se usa FPM con `clear_env = yes` (por defecto), declarar
  `env[APP_ENV] = int` en `www.conf` o `clear_env = no`, si no la variable no
  llega a PHP y el bloque mostrará `unknown`.

Verificar con: `ddev exec printenv APP_ENV` o `php -r 'echo getenv("APP_ENV");'`.

## Colores del bloque

Definidos en `components/environment-info/environment-info.css`:

| Clase | Color |
|-------|-------|
| `dev` | verde |
| `int` | azul |
| `pre` | naranja |
| `staging`, `test` | amarillo |
| `pro`, `prod`, `production` | rojo |
| `unknown` | gris |

## Tests

Tests unitarios en `tests/src/Unit/BuildInfoTest.php`. Requiere
`drupal/core-dev` instalado (`composer require --dev drupal/core-dev`) y se
ejecutan desde la raíz del proyecto:

```bash
ddev exec vendor/bin/phpunit --configuration web/core/phpunit.xml.dist web/modules/custom/environment_info/tests/src/Unit/BuildInfoTest.php
```
