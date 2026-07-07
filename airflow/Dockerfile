# base 이미지는 offline_load.sh로 사전에 docker에 로드되어 있어야 함
ARG AIRFLOW_BASE_IMAGE=apache/airflow:2.11.0
FROM ${AIRFLOW_BASE_IMAGE}

USER root
ARG CS_VER=4.105.1

# 로컬에 같이 들어있는 code-server tar.gz를 사용 (인터넷 접근 X)
# vendor/code-server-*.tar.gz 를 이미지로 복사
COPY vendor/code-server-${CS_VER}-linux-amd64.tar.gz /tmp/code-server.tar.gz

# code-server 설치
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates tar; \
    tar -xzf /tmp/code-server.tar.gz -C /usr/local --strip-components=1 code-server-${CS_VER}-linux-amd64; \
    ln -sf /usr/local/bin/code-server /usr/bin/code-server; \
    rm -f /tmp/code-server.tar.gz; \
    apt-get purge -y --auto-remove; \
    rm -rf /var/lib/apt/lists/*

# airflow 유저 홈/설정 디렉토리 준비 및 권한 부여
RUN mkdir -p \
      /home/airflow/.config/code-server \
      /home/airflow/.local/share/code-server \
      /home/airflow/.local/share/code-server/extensions \
      /home/airflow/.vscode \
      /opt/airflow/logs \
    && chown -R airflow:0 /home/airflow /opt/airflow/logs \
    && chmod -R 770 /opt/airflow/logs

USER airflow
WORKDIR /opt/airflow
