// Despliegue de shamandul/dkvr (codigo de Drupal) en docker-compose y Minikube.
//
// Disparos:
//   - Manual: "Build with Parameters".
//   - Automatico: cron cada ~5 min; solo redespliega si git ls-remote detecta
//     un commit nuevo en el repo upstream (o si FORCE=true).
//
// El workspace es una copia de este mismo repo (docker-compose.yml, k8s/, .env,
// scripts/), asi que el pipeline ejecuta los mismos comandos documentados en el
// README, con la unica diferencia de COMPOSE_PROJECT_NAME (para tocar el stack
// que ya corre en el host) y de que las verificaciones HTTP se hacen desde la
// red del stack (servicio `drupal`) y por la IP de Minikube (Host: drupal.local).

pipeline {
  agent any

  options {
    timestamps()
    disableConcurrentBuilds()
    buildDiscarder(logRotator(numToKeepStr: '30'))
    timeout(time: 90, unit: 'MINUTES')
  }

  parameters {
    choice(name: 'TARGET', choices: ['both', 'compose', 'minikube'], description: 'Entorno(s) a desplegar')
    booleanParam(name: 'FORCE', defaultValue: false, description: 'Desplegar aunque no haya commits nuevos en shamandul/dkvr')
    string(name: 'DRUPAL_GIT_REF', defaultValue: '', description: 'Rama/tag a desplegar (vacio = DRUPAL_GIT_REF de .env)')
    string(name: 'ENABLE_MODULE', defaultValue: '', description: 'Modulo a habilitar por HTTP tras desplegar (vacio = ninguno)')
    booleanParam(name: 'CLEAN', defaultValue: true, description: 'Poda de build cache e imagenes dangling (ahorra disco)')
  }

  triggers {
    cron('H/5 * * * *')
  }

  environment {
    UPSTREAM_URL = 'https://github.com/shamandul/dkvr.git'
    COMPOSE_PROJECT_NAME = 'drupal-kafka'
    KUBECONFIG = '/home/jesus/.kube/config'
    MINIKUBE_HOME = '/home/jesus/.minikube'
  }

  stages {
    stage('Upstream: hay cambios?') {
      steps {
        script {
          def ref = (params.DRUPAL_GIT_REF ?: '').trim()
          if (!ref) {
            ref = sh(script: "sed -n 's/^DRUPAL_GIT_REF=//p' .env | head -1", returnStdout: true).trim() ?: 'main'
          }
          env.GIT_REF = ref
          // Resuelve el sha al que apunta el ref: rama, tag anotado (peeled) o tag ligero.
          def sha = sh(
            script: '''
              s=$(git ls-remote "$UPSTREAM_URL" "refs/heads/$GIT_REF" | head -1 | cut -f1)
              [ -n "$s" ] || s=$(git ls-remote "$UPSTREAM_URL" "refs/tags/$GIT_REF^{}" | head -1 | cut -f1)
              [ -n "$s" ] || s=$(git ls-remote "$UPSTREAM_URL" "refs/tags/$GIT_REF" | head -1 | cut -f1)
              echo "$s"
            ''',
            returnStdout: true
          ).trim()
          if (!sha) {
            error("No se pudo resolver el ref '${ref}' en ${env.UPSTREAM_URL}")
          }
          env.UPSTREAM_SHA = sha
          def last = fileExists('last_deployed_sha.txt') ? readFile('last_deployed_sha.txt').trim() : ''
          env.DEPLOY = 'true'
          if (params.FORCE) {
            echo "FORCE=true -> se redespliega aunque no haya cambios (sha ${sha})"
          } else if (last && last == sha) {
            env.DEPLOY = 'false'
            currentBuild.result = 'NOT_BUILT'
            echo "Sin cambios: ${sha} ya esta desplegado. Usa FORCE=true para redesplegar."
          } else {
            echo "A desplegar: ${sha} (ultimo desplegado: ${last ?: 'ninguno'})"
          }
        }
      }
    }

    stage('Compose: build imagen') {
      when { expression { env.DEPLOY == 'true' && params.TARGET in ['both', 'compose'] } }
      steps {
        sh label: 'docker compose build (CACHEBUST)', script: '''
          docker compose build --build-arg CACHEBUST=$(date +%s) drupal
        '''
      }
    }

    stage('Compose: despliegue') {
      when { expression { env.DEPLOY == 'true' && params.TARGET in ['both', 'compose'] } }
      steps {
        sh label: 'up + reinicio de Varnish', script: '''
          docker compose up -d drupal
          docker compose restart varnish
        '''
        sh label: 'vacia caches de Drupal', script: '''
          T=$(docker compose exec -T postgres psql -U drupal -d drupal -tAc \
            "select string_agg(tablename,',') from pg_tables where schemaname='public' and tablename like 'cache_%'")
          if [ -n "$T" ]; then
            docker compose exec -T postgres psql -U drupal -d drupal -c "TRUNCATE $T;"
          fi
        '''
      }
    }

    stage('Compose: verificacion') {
      when { expression { env.DEPLOY == 'true' && params.TARGET in ['both', 'compose'] } }
      steps {
        sh label: 'HTTP 200 + commit desplegado', script: '''
          code=$(curl -s -o /dev/null -w '%{http_code}' http://drupal/)
          echo "compose http://drupal/ -> $code"
          test "$code" = "200"
          vcode=$(curl -s -o /dev/null -w '%{http_code}' -H 'Host: localhost' http://varnish:6081/)
          echo "varnish -> $vcode"
          head=$(docker compose exec -T drupal \
            git -c safe.directory=/var/www/html -C /var/www/html rev-parse HEAD)
          echo "codigo en la imagen: $head | esperado: $UPSTREAM_SHA"
          test "$head" = "$UPSTREAM_SHA"
        '''
      }
    }

    stage('Minikube: imagen') {
      when { expression { env.DEPLOY == 'true' && params.TARGET in ['both', 'minikube'] } }
      steps {
        sh label: 'API de Minikube accesible', script: '''
          if ! kubectl --request-timeout=15s get ns >/dev/null; then
            echo "No responde el API de Minikube (192.168.49.2:8443)."
            echo "Si el cluster esta parado, levantalo desde el host: minikube start"
            exit 1
          fi
        '''
        // minikube image build necesita SSH a 127.0.0.1:<puerto> (solo visible
        // en el host), asi que se construye directamente contra el dockerd del
        // nodo: tcp://192.168.49.2:2376 con los certificados de ~/.minikube/certs.
        sh label: 'build en el dockerd del nodo (CACHEBUST)', script: '''
          DOCKER_HOST=tcp://192.168.49.2:2376 \
          DOCKER_TLS_VERIFY=1 \
          DOCKER_CERT_PATH=$MINIKUBE_HOME/certs \
          docker build -t drupal-kafka:local \
            --build-arg DRUPAL_GIT_URL=$UPSTREAM_URL \
            --build-arg DRUPAL_GIT_REF=$GIT_REF \
            --build-arg CACHEBUST=$(date +%s) \
            docker/drupal
        '''
      }
    }

    stage('Minikube: despliegue') {
      when { expression { env.DEPLOY == 'true' && params.TARGET in ['both', 'minikube'] } }
      steps {
        sh label: 'kubectl apply + rollout', script: '''
          kubectl apply -f k8s/
          kubectl -n drupal rollout restart deploy/drupal deploy/varnish
          kubectl -n drupal rollout status deploy/drupal --timeout=180s
          kubectl -n drupal rollout status deploy/varnish --timeout=180s
        '''
        sh label: 'vacia caches de Drupal (k8s)', script: '''
          T=$(kubectl exec -T -n drupal deploy/postgres -- psql -U drupal -d drupal -tAc \
            "select string_agg(tablename,',') from pg_tables where schemaname='public' and tablename like 'cache_%'")
          if [ -n "$T" ]; then
            kubectl exec -T -n drupal deploy/postgres -- psql -U drupal -d drupal -c "TRUNCATE $T;"
          fi
        '''
      }
    }

    stage('Minikube: verificacion') {
      when { expression { env.DEPLOY == 'true' && params.TARGET in ['both', 'minikube'] } }
      steps {
        sh label: 'HTTP 200 + commit desplegado', script: '''
          code=$(curl -s -o /dev/null -w '%{http_code}' http://drupal.local/)
          echo "minikube http://drupal.local/ -> $code"
          test "$code" = "200"
          head=$(kubectl -n drupal exec deploy/drupal -- \
            git -c safe.directory=/var/www/html -C /var/www/html rev-parse HEAD)
          echo "codigo en el pod: $head | esperado: $UPSTREAM_SHA"
          test "$head" = "$UPSTREAM_SHA"
        '''
      }
    }

    stage('Habilitar modulo (HTTP)') {
      when {
        expression {
          env.DEPLOY == 'true' && (params.ENABLE_MODULE ?: '').trim()
        }
      }
      steps {
        script {
          if (params.TARGET in ['both', 'compose']) {
            sh label: 'habilitar modulo en compose', script: """
              DRUPAL_HOST_HEADER=drupal python3 scripts/enable_module.py http://drupal ${params.ENABLE_MODULE.trim()}
            """
          }
          if (params.TARGET in ['both', 'minikube']) {
            sh label: 'habilitar modulo en minikube', script: """
              DRUPAL_HOST_HEADER=drupal.local python3 scripts/enable_module.py http://drupal.local ${params.ENABLE_MODULE.trim()}
            """
          }
        }
      }
    }

    stage('Poda de Docker') {
      when { expression { env.DEPLOY == 'true' && params.CLEAN } }
      steps {
        sh label: 'builder/image prune', script: '''
          docker builder prune -f --keep-storage 4GiB || true
          docker image prune -f || true
        '''
      }
    }

    stage('Registrar sha desplegado') {
      when { expression { env.DEPLOY == 'true' } }
      steps {
        sh label: 'guarda last_deployed_sha.txt', script: '''
          printf '%s\n' "$UPSTREAM_SHA" > last_deployed_sha.txt
          cat last_deployed_sha.txt
        '''
      }
    }
  }

  post {
    failure {
      echo 'Despliegue fallido: revisa la etapa en rojo. last_deployed_sha.txt NO se actualiza, asi que el proximo cron lo reintenta.'
    }
  }
}
