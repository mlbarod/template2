# Compose 실행 진입점입니다.
COMPOSE_DEV=docker compose -f docker-compose.dev.yml
COMPOSE_OIDC=docker compose -f docker-compose.oidc.yml
COMPOSE_PROD=docker compose -f docker-compose.yml

# infra는 재빌드 빈도가 낮은 기반 서비스만 포함합니다.
# - DB: airflow-postgres
# - Airflow: airflow-init, airflow-webserver, airflow-scheduler
# - FTP: ftp
# - Monitoring: OIDC/prod에서 prometheus, node-exporter, cadvisor, grafana
INFRA_SERVICES=airflow-postgres airflow-init airflow-webserver airflow-scheduler ftp
INFRA_BUILD_SERVICES=airflow-init airflow-webserver airflow-scheduler
MONITORING_SERVICES=prometheus node-exporter cadvisor grafana
OIDC_INFRA_SERVICES=$(INFRA_SERVICES) $(MONITORING_SERVICES)
PROD_INFRA_SERVICES=$(INFRA_SERVICES) $(MONITORING_SERVICES)

# app은 실제 애플리케이션 기능을 구성하는 서비스입니다.
# dev는 로컬 dummy 외부계(adfs)를 app으로 취급합니다.
DEV_APP_SERVICES=adfs minio minio-init api web nginx
DEV_APP_BUILD_SERVICES=adfs api web

# OIDC/prod는 실제 연동 환경이므로 dummy adfs 없이 app 서비스만 다룹니다.
OIDC_APP_SERVICES=minio minio-init api web nginx
OIDC_APP_BUILD_SERVICES=api web
PROD_APP_SERVICES=minio minio-init api web nginx
PROD_APP_BUILD_SERVICES=api web

.PHONY: \
	network \
	dev dev-app-up dev-app-build dev-app-down dev-infra-up dev-infra-build dev-infra-down \
	oidc oidc-app-up oidc-app-build oidc-app-down oidc-infra-up oidc-infra-build oidc-infra-down \
	prod prod-app-up prod-app-build prod-app-down prod-infra-up prod-infra-build prod-infra-down \
	down test-api check-api makemigrations-check \
	y5push

# shared-net은 compose 파일에서 external network로 사용합니다.
network:
	docker network create shared-net 2>/dev/null || true

# dev 기본 실행: API 의존 DB는 compose가 함께 올리고, Airflow/FTP는 제외합니다.
dev:
	$(MAKE) dev-app-up

# dev app을 올립니다. api 의존성은 compose가 확인하므로 DB 준비 이후 API가 시작됩니다.
dev-app-up: network
	$(COMPOSE_DEV) up $(DEV_APP_SERVICES)

# dev app 이미지/빌드 산출물만 다시 빌드합니다.
dev-app-build: network
	$(COMPOSE_DEV) build $(DEV_APP_BUILD_SERVICES)

# dev app 컨테이너만 중지하고 제거합니다. volume과 network는 삭제하지 않습니다.
dev-app-down:
	$(COMPOSE_DEV) stop $(DEV_APP_SERVICES)
	$(COMPOSE_DEV) rm -f $(DEV_APP_SERVICES)

# dev infra만 올립니다.
dev-infra-up: network
	$(COMPOSE_DEV) up -d $(INFRA_SERVICES)

# dev infra 이미지 중 빌드가 필요한 Airflow 이미지만 다시 빌드합니다.
dev-infra-build: network
	$(COMPOSE_DEV) build $(INFRA_BUILD_SERVICES)

# dev infra 컨테이너만 중지하고 제거합니다. DB volume은 삭제하지 않습니다.
dev-infra-down:
	$(COMPOSE_DEV) stop $(INFRA_SERVICES)
	$(COMPOSE_DEV) rm -f $(INFRA_SERVICES)

# OIDC 전체 실행: infra를 먼저 올린 뒤 app을 올립니다.
oidc:
	$(MAKE) oidc-infra-up
	$(MAKE) oidc-app-up

# OIDC app만 올립니다.
oidc-app-up: network
	$(COMPOSE_OIDC) up -d --no-deps $(OIDC_APP_SERVICES)

# OIDC app 이미지/빌드 산출물만 다시 빌드합니다.
oidc-app-build: network
	$(COMPOSE_OIDC) build $(OIDC_APP_BUILD_SERVICES)

# OIDC app 컨테이너만 중지하고 제거합니다.
oidc-app-down:
	$(COMPOSE_OIDC) stop $(OIDC_APP_SERVICES)
	$(COMPOSE_OIDC) rm -f $(OIDC_APP_SERVICES)

# OIDC infra만 올립니다.
oidc-infra-up: network
	$(COMPOSE_OIDC) up -d $(OIDC_INFRA_SERVICES)

# OIDC infra 이미지 중 빌드가 필요한 Airflow 이미지만 다시 빌드합니다.
oidc-infra-build: network
	$(COMPOSE_OIDC) build $(INFRA_BUILD_SERVICES)

# OIDC infra 컨테이너만 중지하고 제거합니다.
oidc-infra-down:
	$(COMPOSE_OIDC) stop $(OIDC_INFRA_SERVICES)
	$(COMPOSE_OIDC) rm -f $(OIDC_INFRA_SERVICES)

# prod 전체 실행: infra를 먼저 올린 뒤 app을 올립니다.
prod:
	$(MAKE) prod-infra-up
	$(MAKE) prod-app-up

# prod app만 올립니다.
prod-app-up: network
	$(COMPOSE_PROD) up -d --no-deps $(PROD_APP_SERVICES)

# prod app 이미지/빌드 산출물만 다시 빌드합니다.
prod-app-build: network
	$(COMPOSE_PROD) build $(PROD_APP_BUILD_SERVICES)

# prod app 컨테이너만 중지하고 제거합니다.
prod-app-down:
	$(COMPOSE_PROD) stop $(PROD_APP_SERVICES)
	$(COMPOSE_PROD) rm -f $(PROD_APP_SERVICES)

# prod infra만 올립니다.
prod-infra-up: network
	$(COMPOSE_PROD) up -d $(PROD_INFRA_SERVICES)

# prod infra 이미지 중 빌드가 필요한 Airflow 이미지만 다시 빌드합니다.
prod-infra-build: network
	$(COMPOSE_PROD) build $(INFRA_BUILD_SERVICES)

# prod infra 컨테이너만 중지하고 제거합니다.
prod-infra-down:
	$(COMPOSE_PROD) stop $(PROD_INFRA_SERVICES)
	$(COMPOSE_PROD) rm -f $(PROD_INFRA_SERVICES)

# 모든 실행 진입점의 compose project를 내립니다.
down:
	$(COMPOSE_DEV) down
	$(COMPOSE_OIDC) down
	$(COMPOSE_PROD) down

# 개발 API 컨테이너 기준 검증 명령입니다.
test-api:
	$(COMPOSE_DEV) exec -T api python manage.py test

check-api:
	$(COMPOSE_DEV) exec -T api python manage.py check

makemigrations-check:
	$(COMPOSE_DEV) exec -T api python manage.py makemigrations --check --dry-run

# 현재 변경사항 전체를 커밋한 뒤 y5 브랜치로 푸시합니다.
# 사용: make y5push msg="커밋 메시지"
y5push:
	@test -n "$(strip $(msg))" || (echo '사용: make y5push msg="커밋 메시지"'; exit 1)
	./y5push "$(msg)"
