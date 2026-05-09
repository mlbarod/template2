# Auth 모듈

Auth는 OIDC 기반 로그인과 Django session 관리를 담당합니다.

## 기능 요약

- OIDC 로그인 시작
- OIDC callback 처리
- 사용자 생성/갱신
- Django session login/logout
- 현재 사용자 정보 조회
- redirect target 검증

## 동작 흐름

1. 프론트가 로그인 endpoint를 호출합니다.
2. 서버가 state와 nonce를 생성합니다.
3. 사용자는 ADFS authorize URL로 이동합니다.
4. ADFS가 callback endpoint로 `id_token`을 전달합니다.
5. 서버가 state와 nonce를 검증합니다.
6. claim으로 `User`를 생성하거나 갱신합니다.
7. Django session을 만들고 프론트로 redirect합니다.

## Account와의 연결

로그인 후 `/api/v1/auth/me`는 사용자 정보와 소속 상태를 반환합니다. 프론트는 이 값으로 온보딩 또는 소속 재확인 dialog를 띄울지 결정합니다.

## 로컬 개발

로컬에서는 `apps/adfs_dummy`가 ADFS 역할을 합니다.

## 관련 API

- `docs/api/auth.md`

## 관련 코드

- `apps/api/api/auth/views.py`
- `apps/api/api/auth/callback_urls.py`
- `apps/api/api/auth/urls.py`
- `apps/api/api/auth/selectors.py`
- `apps/api/api/auth/services/oidc.py`
- `apps/api/api/auth/services/oidc_utils.py`
- `apps/api/api/auth/services/authentication.py`
- `apps/web/src/features/auth`
