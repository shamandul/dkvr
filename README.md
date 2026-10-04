# Drupal + Varnish + Redis + Kafka + PostgreSQL en Minikube

## Requisitos

- Docker
- Minikube
- kubectl

## Código de Drupal desde GitHub

La imagen de Drupal se construye clonando un repositorio público de GitHub
(docroot completo con `core/`, `vendor/`, `composer.json`). Configúralo en `.env`:

```dotenv
DRUPAL_GIT_URL=https://github.com/usuario/repo.git
DRUPAL_GIT_REF=main
```

El Dockerfile detecta el document root automáticamente en la raíz del repo,
en `web/` o en `docroot/` (falla el build si no encuentra `index.php`).
Si el repo no incluye `vendor/`, se ejecuta `composer install` durante el
build (se usa la caché de Composer entre builds).

### docker-compose

```bash
docker compose build drupal
docker compose up -d
# http://localhost:8080
```

### Minikube

El build debe ejecutarse con el contexto dentro de `docker/drupal`:

```bash
cd docker/drupal
minikube image build -f Dockerfile -t drupal-kafka:local \
  --build-opt=build-arg=DRUPAL_GIT_URL=https://github.com/usuario/repo.git \
  --build-opt=build-arg=DRUPAL_GIT_REF=main .
```

(Alternativa: `eval $(minikube docker-env)` y después `docker compose build drupal`
— en ese caso el build se hace contra el demonio de Docker de Minikube.)

Para reconstruir tras cambiar el código del repo, repite el `image build`
(y `kubectl rollout restart deployment/drupal -n drupal` si la imagen ya estaba
desplegada).

### Variables de entorno de Drupal

| Variable | Descripción | Default |
| --- | --- | --- |
| `DRUPAL_GIT_URL` | Repo GitHub con el docroot (build) | — (obligatoria) |
| `DRUPAL_GIT_REF` | Rama/tag a clonar (build) | `main` |
| `DRUPAL_SETTINGS_MODE` | Generar `settings.php`: `auto`/`force`/`skip` | `auto` |
| `DRUPAL_TRUSTED_HOSTS` | Hosts de confianza, separados por coma | `drupal.local,localhost,127.0.0.1` |
| `DRUPAL_HASH_SALT` | Hash salt de Drupal (si vacío, se genera y persiste) | generado |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Conexión PostgreSQL | `postgres:5432` |
| `REDIS_HOST`, `REDIS_PORT` | Redis para caché (si el módulo está habilitado) | `redis:6379` |
| `KAFKA_HOST` | Broker Kafka (`kafka:9092`) | — |
| `DRUPAL_CONFIG_SYNC_DIR` | Directorio de sincronización de config | sin definir |
| `DRUPAL_FILE_PRIVATE_PATH` | Ficheros privados | sin definir |

`DRUPAL_SETTINGS_MODE=auto` genera `sites/default/settings.php` solo si no
existe (si el repo ya trae uno, se respeta); `force` lo sobreescribe siempre;
`skip` no lo toca. El repo de ejemplo trae el `settings.php` de Drupal por
defecto, sin `$databases`, así que `.env` (compose) y `k8s/drupal.yaml` usan
`force` para inyectar la conexión a PostgreSQL. En producción inyecta los
secretos con un Secret de Kubernetes en lugar de valores fijos en
`k8s/drupal.yaml`.


## Actualizar el código

La imagen clona el repo durante el build, y BuildKit **reutiliza la capa
`git clone` si no cambian `DRUPAL_GIT_URL`/`DRUPAL_GIT_REF`**: con un rebuild
normal seguirías sirviendo el código anterior. Para entrar el commit nuevo hay
que pasar el build arg `CACHEBUST` (solo cuando hayas subido cambios; invalida
el clone sin tocar las capas de apt/pecl, que van antes del `COPY`).

### docker-compose

```bash
docker compose build --build-arg CACHEBUST=$(date +%s) drupal
docker compose up -d drupal
docker compose restart varnish
```

### Minikube

```bash
cd docker/drupal
minikube image build -f Dockerfile -t drupal-kafka:local \
  --build-opt=build-arg=DRUPAL_GIT_URL=https://github.com/usuario/repo.git \
  --build-opt=build-arg=DRUPAL_GIT_REF=main \
  --build-opt=build-arg=CACHEBUST=$(date +%s) .
kubectl apply -f k8s/drupal.yaml
kubectl rollout restart deployment/drupal -n drupal
kubectl rollout status deployment/drupal -n drupal
kubectl rollout restart deployment/varnish -n drupal
```

Si cambiaste de rama/tag, actualiza también `DRUPAL_GIT_REF` (`.env` en
compose; el build arg en Minikube).

### Limpiar las cachés de Drupal

Drupal guarda su caché en PostgreSQL (el módulo redis no está en el repo), así
que vacía las tablas `cache_*`; si no, seguirás viendo la versión anterior:

```bash
# docker-compose
T=$(docker compose exec -T postgres psql -U drupal -d drupal -tAc \
  "select string_agg(tablename,',') from pg_tables where schemaname='public' and tablename like 'cache_%'")
docker compose exec -T postgres psql -U drupal -d drupal -c "TRUNCATE $T;"

# Minikube
T=$(kubectl exec -T -n drupal deploy/postgres -- psql -U drupal -d drupal -tAc \
  "select string_agg(tablename,',') from pg_tables where schemaname='public' and tablename like 'cache_%'")
kubectl exec -T -n drupal deploy/postgres -- psql -U drupal -d drupal -c "TRUNCATE $T;"
```

### Comprobar que está desplegado

```bash
docker compose exec drupal sh -c 'grep -n "lo-que-cambiaste" /var/www/html/web/ruta/fichero'
curl -sI http://localhost:8080/
curl --resolve drupal.local:80:$(minikube ip) http://drupal.local/
```

Si tu cambio añade o habilita módulos o modifica config exportada, hay que
habilitarlos/importarlos desde la UI o con drush (la imagen lleva
`/usr/local/bin/drush`):

```bash
docker compose exec drupal drush en environment_info
docker compose exec drupal drush cim
docker compose exec drupal drush uli --uri=http://localhost:8080
```

## Despliegue

```bash
minikube start
minikube addons enable ingress
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/
kubectl get pods -n drupal
```

Obtén la IP:

```bash
minikube ip
```

Añade en `/etc/hosts`:

```text
<MINIKUBE_IP> drupal.local
```

Abre:

http://drupal.local

`sites/default/files` (subidas y `files/config/sync`) persiste entre
redespliegues: volumen `drupal_files` en compose y PVC `drupal-files` en k8s,
montados en `/var/www/html/web/sites/default/files` (fijados al docroot `web`
del repo; si cambia el docroot, ajusta `docker-compose.yml` y `k8s/drupal.yaml`).

y completa el instalador de Drupal (perfil **standard**). La conexión a la base
de datos ya está en `settings.php`, así que solo pide idioma, instala el perfil
y pide los datos del sitio.

## Varnish

`docker/varnish/default.vcl` (compose) y el ConfigMap `k8s/varnish-config`
comparten el mismo VCL: solo se cachean respuestas GET/HEAD anónimas de 200 que
Drupal marca como reutilizables (`X-Drupal-Cache: HIT` o `Cache-Control:
public`), con TTL de 5 minutos. Nunca se cachean redirecciones, respuestas con
`Set-Cookie`, peticiones con sesión de Drupal (`SESS*`), las rutas `/admin`,
`/user`, `/batch` ni los scripts `install.php`, `update.php`, `cron.php`.

## CI/CD con Jenkins

Jenkins vive como servicio del propio stack, pero solo con el profile `ci`
(no arranca en un `docker compose up -d` normal). Requisito: Minikube
levantado (el servicio se conecta a su red externa `minikube`).

```bash
minikube start                      # si no lo esta ya
docker compose --profile ci build jenkins
docker compose --profile ci up -d jenkins
```

- UI: http://localhost:8081 — usuario `admin`, contraseña
  `JENKINS_ADMIN_PASSWORD` de `.env` (`Kafka123!`). Puerto de agentes: 50000.
- Configuración como código: `docker/jenkins/jenkins.yaml` (JCasC) crea el
  usuario admin y la job **`dkvr-deploy`**, que toma el `Jenkinsfile` de este
  mismo repo publicado en el repo público `https://github.com/shamandul/dkvr.git`
  (rama `ci`: este stack de despliegue, clonable sin credenciales).
- Imagen: `docker/jenkins/Dockerfile` = Jenkins LTS + docker CLI/compose v2,
  kubectl, minikube, git, python3 y los plugins JCasC/job-dsl/git/pipeline.
- El contenedor monta `/var/run/docker.sock` (grupo `DOCKER_GID` de `.env`),
  `~/.kube` y `~/.minikube` con sus rutas originales (el kubeconfig usa rutas
  absolutas de certificados), y se une a la red `minikube` para alcanzar el
  nodo (sin ella, `192.168.49.2` no es enrutable desde otra red Docker).

### Qué hace la job

Parámetros (`Build with Parameters`):

| Parámetro | Default | Descripción |
| --- | --- | --- |
| `TARGET` | `both` | Entorno(s): `both`, `compose`, `minikube` |
| `FORCE` | no | Desplegar aunque no haya commits nuevos |
| `DRUPAL_GIT_REF` | vacío | Rama/tag a desplegar (vacío = `DRUPAL_GIT_REF` de `.env`) |
| `ENABLE_MODULE` | vacío | Módulo a habilitar por HTTP (p. ej. `environment_info`) |
| `CLEAN` | sí | Poda de build cache e imágenes dangling |

Etapas (con `TARGET=both`):

1. **Upstream**: `git ls-remote` de `shamandul/dkvr` (rama, tag anotado o
   tag ligero). Si el sha no cambió y no hay `FORCE`, el build termina como
   `NOT_BUILT` sin tocar nada; si cambió (o hay `FORCE`), continúa.
2. **Compose**: `docker compose build --build-arg CACHEBUST=... drupal`,
   `up -d drupal`, `restart varnish`, vaciado de `cache_*` y verificación
   (HTTP 200 contra `http://drupal/` en la red del stack + `git rev-parse
   HEAD` dentro del contenedor = sha esperado).
3. **Minikube**: comprobación del API (`kubectl`), `docker build` contra el
   dockerd del nodo (`tcp://192.168.49.2:2376` + certificados de
   `~/.minikube/certs` — no se usa `minikube image build` porque su SSH
   apunta a `127.0.0.1:<puerto>`, invisible desde el contenedor),
   `kubectl apply -f k8s/`, `rollout restart/status` de drupal y varnish,
   vaciado de `cache_*` y verificación (HTTP 200 en `drupal.local` + `git
   rev-parse HEAD` en el pod).
4. Opcional (`ENABLE_MODULE`): `scripts/enable_module.py` (login admin +
   `/admin/modules`) en cada entorno elegido.
5. Poda de Docker (`builder prune --keep-storage 4GiB` + `image prune`) y
   registro del sha en `last_deployed_sha.txt` (gitignorado). El sha solo se
   guarda si todas las etapas anteriores terminaron bien.

### Disparo automático

El `Jenkinsfile` declara `cron('H/5 * * * *')`: cada ~5 minutos consulta el
repo upstream y solo despliega si hay commit nuevo (si no, `NOT_BUILT`).
**La primera ejecución es siempre manual**, porque el cron se registra al
cargar el Jenkinsfile. No hay webhooks: Jenkins no es accesible desde
Internet; para push-to-deploy haría falta un túnel/URL pública.

### Notas

- La job usa `COMPOSE_PROJECT_NAME=drupal-kafka` (toca el mismo stack que el
  host) y solo ejecuta `up -d drupal` (nunca `up` completo): así no se
  resuelven los bind mounts del host desde dentro del contenedor (el VCL de
  Varnish se toca con `restart`, sin recrear).
- `DRUPAL_TRUSTED_HOSTS` incluye `drupal` para poder verificar y habilitar
  módulos por HTTP desde el contenedor de Jenkins en la red de compose.
- Si el clúster está parado, la etapa de Minikube falla con un mensaje
  claro: levántalo con `minikube start` en el host y vuelve a lanzar el build.

## Arquitectura

Internet -> Ingress -> Varnish -> Drupal -> PostgreSQL
                              |
                              +-> Redis
                              |
                              +-> Kafka

## Nota

Este proyecto es una base de desarrollo para Minikube. Para producción habría que
añadir secretos, persistencia adecuada, TLS, recursos/limits, health checks,
replicación, seguridad de Kafka y una estrategia de despliegue de Drupal.
