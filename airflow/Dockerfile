ARG AIRFLOW_BASE_IMAGE=apache/airflow:2.11.0
FROM ${AIRFLOW_BASE_IMAGE}

ARG APT_DEBIAN_REPOSITORY=
ARG APT_DEBIAN_CODENAME=bookworm
ARG APT_DEBIAN_ARCH=amd64
ARG PIP_INDEX_URL=
ARG PIP_EXTRA_INDEX_URL=
ARG PIP_TRUSTED_HOST=
ARG INSTALL_BIGDATAQUERY_PYTHON=false
ARG INSTALL_BIGDATAQUERY_ODBC=false
ARG BIGDATAQUERY_ODBC_DEB_URL=

USER root

# 사내망 빌드에서는 Airflow 공식 이미지 안의 apt/pip source를 내부 mirror로 교체한다.
RUN if [ -n "$APT_DEBIAN_REPOSITORY" ]; then \
        printf 'deb [arch=%s] %s %s main\n' "$APT_DEBIAN_ARCH" "$APT_DEBIAN_REPOSITORY" "$APT_DEBIAN_CODENAME" > /etc/apt/sources.list; \
        rm -f /etc/apt/sources.list.d/*; \
    fi

RUN if [ -n "$PIP_INDEX_URL" ]; then \
        printf '[global]\nindex-url = %s\n' "$PIP_INDEX_URL" > /etc/pip.conf; \
        if [ -n "$PIP_EXTRA_INDEX_URL" ]; then \
            printf 'extra-index-url = %s\n' "$PIP_EXTRA_INDEX_URL" >> /etc/pip.conf; \
        fi; \
        if [ -n "$PIP_TRUSTED_HOST" ]; then \
            first_host=true; \
            for host in $PIP_TRUSTED_HOST; do \
                if [ "$first_host" = "true" ]; then \
                    printf 'trusted-host = %s\n' "$host" >> /etc/pip.conf; \
                    first_host=false; \
                else \
                    printf '    %s\n' "$host" >> /etc/pip.conf; \
                fi; \
            done; \
        fi; \
    fi

# BigDataQuery ODBC는 사내망 빌드에서만 설치하고, DSN 파일은 운영 mount로 주입한다.
RUN if [ "$INSTALL_BIGDATAQUERY_ODBC" = "true" ]; then \
        if [ -z "$BIGDATAQUERY_ODBC_DEB_URL" ]; then \
            echo "BIGDATAQUERY_ODBC_DEB_URL is required when INSTALL_BIGDATAQUERY_ODBC=true" >&2; \
            exit 1; \
        fi; \
        apt-get update; \
        apt-get install -y --no-install-recommends \
            ca-certificates \
            unixodbc \
            unixodbc-dev \
            wget; \
        wget -O /tmp/clouderaimpalaodbc.deb "$BIGDATAQUERY_ODBC_DEB_URL"; \
        dpkg -i /tmp/clouderaimpalaodbc.deb || apt-get install -f -y --no-install-recommends; \
        rm -f /tmp/clouderaimpalaodbc.deb; \
        mkdir -p /opt/cloudera/impalaodbc/lib/64/en-US/; \
        if [ -d /opt/cloudera/impalaodbc/ErrorMessages/en-US ]; then \
            cp /opt/cloudera/impalaodbc/ErrorMessages/en-US/* /opt/cloudera/impalaodbc/lib/64/en-US/; \
        fi; \
        rm -rf /var/lib/apt/lists/*; \
    fi

RUN if [ "$INSTALL_BIGDATAQUERY_PYTHON" = "true" ]; then \
        python -m pip install --no-cache-dir bigdataquery; \
    fi

RUN mkdir -p /opt/airflow/logs /usr/local/odbc \
    && chown -R airflow:0 /opt/airflow/logs \
    && chmod -R 770 /opt/airflow/logs

ENV ODBCINI=/usr/local/odbc/odbc.ini \
    ODBCSYSINI=/usr/local/odbc \
    CLOUDERAIMPALAINI=/etc/cloudera.impalaodbc.ini

USER airflow
WORKDIR /opt/airflow
