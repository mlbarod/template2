ARG PYTHON_BASE_IMAGE=python:3.12-bookworm
FROM ${PYTHON_BASE_IMAGE} AS base

# - PYTHONDONTWRITEBYTECODE=1 .pyc 캐시 파일 생성 방지 → 이미지가 깔끔해짐
# - PYTHONUNBUFFERED=1 표준 출력 버퍼링 비활성화 → docker logs 에 즉시 표시
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1  

WORKDIR /app

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
