# Vite 빌드 + 정적 프리뷰를 위한 멀티 스테이지 Dockerfile

ARG NODE_BASE_IMAGE=node:20-alpine
FROM ${NODE_BASE_IMAGE} AS deps
ARG ALPINE_REPOSITORY_MIRROR=
ARG NPM_REGISTRY=
ARG NPM_STRICT_SSL=true
WORKDIR /app
RUN if [ -n "$ALPINE_REPOSITORY_MIRROR" ]; then \
        sed -i "s@https://dl-cdn.alpinelinux.org/alpine@${ALPINE_REPOSITORY_MIRROR}@g" /etc/apk/repositories; \
    fi
RUN if [ -n "$NPM_REGISTRY" ]; then \
        npm config set registry "$NPM_REGISTRY"; \
    fi \
    && npm config set strict-ssl "$NPM_STRICT_SSL"
COPY package.json package-lock.json ./
RUN npm install --legacy-peer-deps

FROM ${NODE_BASE_IMAGE} AS builder
WORKDIR /app
ENV NODE_ENV=production
ARG VITE_BACKEND_URL=/
ARG VITE_AIRFLOW_BASE_URL=/airflow
ARG VITE_AIRFLOW_USERNAME=airflow
ARG VITE_AIRFLOW_PASSWORD=airflow
ARG VITE_PORTAL_PMX_URL=
ARG VITE_PORTAL_MOSAIC_URL=
ARG VITE_PORTAL_CONFLUENCE_URL=
ARG VITE_DEFECT_SPIDER_URL=
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV VITE_BACKEND_URL=${VITE_BACKEND_URL}
ENV VITE_AIRFLOW_BASE_URL=${VITE_AIRFLOW_BASE_URL}
ENV VITE_AIRFLOW_USERNAME=${VITE_AIRFLOW_USERNAME}
ENV VITE_AIRFLOW_PASSWORD=${VITE_AIRFLOW_PASSWORD}
ENV VITE_PORTAL_PMX_URL=${VITE_PORTAL_PMX_URL}
ENV VITE_PORTAL_MOSAIC_URL=${VITE_PORTAL_MOSAIC_URL}
ENV VITE_PORTAL_CONFLUENCE_URL=${VITE_PORTAL_CONFLUENCE_URL}
ENV VITE_DEFECT_SPIDER_URL=${VITE_DEFECT_SPIDER_URL}
RUN npm run build

FROM ${NODE_BASE_IMAGE} AS runner
ARG ALPINE_REPOSITORY_MIRROR=
ARG NPM_REGISTRY=
ARG NPM_STRICT_SSL=true
WORKDIR /app
ENV NODE_ENV=production
RUN if [ -n "$ALPINE_REPOSITORY_MIRROR" ]; then \
        sed -i "s@https://dl-cdn.alpinelinux.org/alpine@${ALPINE_REPOSITORY_MIRROR}@g" /etc/apk/repositories; \
    fi
RUN if [ -n "$NPM_REGISTRY" ]; then \
        npm config set registry "$NPM_REGISTRY"; \
    fi \
    && npm config set strict-ssl "$NPM_STRICT_SSL"
COPY --from=builder /app/dist ./dist
RUN npm install -g serve
EXPOSE 3000
CMD ["serve", "-s", "dist", "-l", "3000"]
