FROM jenkins/jenkins:lts-jdk17

USER root

# Utilidades base: git (checkout del repo de despliegue), python3 (scripts HTTP
# de Drupal), openssh-client y curl/ca-certificates (minikube -> nodo, kubectl).
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git gnupg openssh-client python3 \
    && rm -rf /var/lib/apt/lists/*

# Docker CLI + plugin compose v2 (habla con el docker.sock del host).
RUN install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/*

# kubectl (version estable)
RUN KVER="$(curl -fsSL https://dl.k8s.io/release/stable.txt)" \
    && curl -fsSLo /usr/local/bin/kubectl "https://dl.k8s.io/release/${KVER}/bin/linux/amd64/kubectl" \
    && chmod +x /usr/local/bin/kubectl

# minikube (image build y status del perfil local)
RUN curl -fsSLo /usr/local/bin/minikube https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64 \
    && chmod +x /usr/local/bin/minikube

# Plugins de Jenkins (JCasC + job-dsl para la job, git/SCM, pipeline)
COPY --chown=jenkins:jenkins plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt

USER jenkins
