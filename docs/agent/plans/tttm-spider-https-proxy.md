# ExecPlan: TTTM Spider HTTPS proxy

## 목표
- HTTPS 앱 안에서 TTTM Spider HTTP 페이지를 iframe으로 직접 로드하지 않게 한다.
- 브라우저에는 same-origin HTTPS 경로만 노출해 mixed content로 인한 `주의 요함` 표시를 피한다.

## 현재 상태
- 프론트 `TttmSpiderPage`가 `http://10.172.60.187:32710`을 iframe `src`로 직접 사용한다.
- prod nginx는 `/tttm-spider/` 프록시 경로가 없다.
- prod nginx 설정은 정적 conf mount를 사용하므로 upstream 값을 env로 바꾸려면 nginx template envsubst가 필요하다.

## 범위
- 수정: `deploy/nginx/default.prod.conf`
- 수정: `compose/prod.app.yml`
- 수정: `apps/web/src/features/tttm-spider/pages/TttmSpiderPage.jsx`
- 수정: `docs/configuration.md`
- 제외: TTTM Spider 원본 서비스 HTTPS화, TTTM 내부 asset URL rewrite 정밀 튜닝

## 설계
- prod nginx에 `/tttm-spider/` location을 추가하고 내부 upstream으로 프록시한다.
- nginx 공식 이미지의 `/etc/nginx/templates/default.conf.template` 렌더링을 사용한다.
- envsubst는 `TTTM_SPIDER_UPSTREAM`만 치환하도록 `NGINX_ENVSUBST_FILTER`를 제한한다.
- React iframe은 `/tttm-spider/`를 사용한다.

## 실행 단계
- [x] nginx TTTM Spider upstream/location을 추가한다.
- [x] prod compose nginx mount를 template 방식으로 바꾸고 upstream env를 추가한다.
- [x] React iframe URL을 same-origin 경로로 변경한다.
- [x] compose/nginx/frontend 경계 검증을 실행한다.

## 검증
- `bash scripts/agent/check_compose_configs.sh`
- nginx template 렌더링 후 `nginx -t`
- `cd apps/web && npm run agent:audit:web-boundary`

## 위험과 대응
- 위험: TTTM 원본 페이지가 내부에서 절대 HTTP asset URL을 렌더링하면 mixed content가 남을 수 있다.
- 대응: 1차로 proxy redirect를 추가하고, 필요 시 TTTM 원본 서비스의 base URL 또는 nginx rewrite를 후속 조정한다.
- 위험: nginx template envsubst가 `$host` 같은 nginx 변수를 잘못 치환할 수 있다.
- 대응: `NGINX_ENVSUBST_FILTER`를 `TTTM_SPIDER_UPSTREAM`으로 제한한다.

## 진행 기록
- 2026-07-07: `/tttm-spider/` same-origin HTTPS proxy와 iframe URL 변경을 적용했다.
- 2026-07-07: compose config, nginx template syntax check, frontend boundary audit는 통과했다.
- 2026-07-07: UI audit는 기존 `l3-spider` raw color/inline style 후보로 실패했으며 이번 변경 범위와 무관하다.
- 2026-07-07: `npm run web:build`는 기존 `apps/web/vite.config.mjs`의 `STAGING_HOST is not defined` 오류로 실패했다.
