ARG PYTHON_BASE_IMAGE=python:3.12-bullseye
FROM ${PYTHON_BASE_IMAGE} AS base

ARG APT_DEBIAN_REPOSITORY=
ARG APT_DEBIAN_CODENAME=bullseye
ARG APT_DEBIAN_ARCH=amd64
ARG PIP_INDEX_URL=
ARG PIP_TRUSTED_HOST=

# - PYTHONDONTWRITEBYTECODE=1 .pyc 캐시 파일 생성 방지 → 이미지가 깔끔해짐
# - PYTHONUNBUFFERED=1 표준 출력 버퍼링 비활성화 → docker logs 에 즉시 표시
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1  

WORKDIR /app

RUN if [ -n "$APT_DEBIAN_REPOSITORY" ]; then \
        printf 'deb [arch=%s] %s %s main\n' "$APT_DEBIAN_ARCH" "$APT_DEBIAN_REPOSITORY" "$APT_DEBIAN_CODENAME" > /etc/apt/sources.list; \
        rm -f /etc/apt/sources.list.d/*; \
    fi

RUN if [ -n "$PIP_INDEX_URL" ]; then \
        printf '[global]\nindex-url = %s\n' "$PIP_INDEX_URL" > /etc/pip.conf; \
        if [ -n "$PIP_TRUSTED_HOST" ]; then \
            printf 'trusted-host = %s\n' "$PIP_TRUSTED_HOST" >> /etc/pip.conf; \
        fi; \
    fi

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x ./entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
