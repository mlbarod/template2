# Vite 빌드 + 정적 프리뷰를 위한 멀티 스테이지 Dockerfile

FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install --legacy-peer-deps

FROM node:20-alpine AS builder
WORKDIR /app
ENV NODE_ENV=production
ARG VITE_BACKEND_URL=/
ARG VITE_AIRFLOW_BASE_URL=/airflow
ARG VITE_AIRFLOW_USERNAME=airflow
ARG VITE_AIRFLOW_PASSWORD=airflow
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV VITE_BACKEND_URL=${VITE_BACKEND_URL}
ENV VITE_AIRFLOW_BASE_URL=${VITE_AIRFLOW_BASE_URL}
ENV VITE_AIRFLOW_USERNAME=${VITE_AIRFLOW_USERNAME}
ENV VITE_AIRFLOW_PASSWORD=${VITE_AIRFLOW_PASSWORD}
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/dist ./dist
RUN npm install -g serve
EXPOSE 3000
CMD ["serve", "-s", "dist", "-l", "3000"]
