# ExecPlan: L3 Spider Guide Assets

## 목표
- `apps/web/public/l3-spider/user_guide.html`이 참조하는 캡처 이미지를 public 서빙 경로에서 정상 로드되게 한다.
- 변경된 Summary 화면은 현재 UI 기준 캡처로 갱신한다.

## 현재 상태
- `user_guide.html`은 `l3-spider-guide-assets/*.png` 상대 경로를 참조한다.
- `apps/web/public/l3-spider/l3-spider-guide-assets/` 폴더가 없어 이미지 요청이 실패한다.
- 기존 참고 이미지는 `docs/examples/l3-spider-guide-assets/`에 있다.

## 범위
- 수정/추가: `apps/web/public/l3-spider/**` 설명서 asset 경로와 필요한 이미지 파일
- 참고: `docs/examples/l3-spider-guide-assets/**`
- 수정하지 않음: L3 Spider 앱 로직, API, 백엔드, 설명서 본문 대규모 재작성

## 설계
- HTML이 이미 사용하는 상대 경로를 유지하고, 동일한 하위 폴더를 public 경로에 생성한다.
- 기존 캡처 이미지는 동일 파일명으로 복사한다.
- Summary 이미지는 가능한 경우 dev 서버에서 새로 캡처해 `summary-overview.png`에 반영한다.
- auth/data 환경 때문에 캡처가 불가능하면 복사본 반영 후 실패 사유를 기록한다.

## 실행 단계
- [x] public asset 폴더 생성 및 기존 이미지 복사
- [x] Summary 화면 새 캡처 가능 여부 확인
- [x] 새 Summary 캡처 반영 또는 캡처 불가 사유 기록
- [x] HTML 이미지 URL이 200으로 응답하는지 확인
- [x] frontend 검증 실행

## 검증
- `curl -I http://localhost:3001/l3-spider/l3-spider-guide-assets/summary-overview.png`
- `npm run agent:audit:ui`
- `npm run web:lint`
- `npm run web:build`

## 위험과 대응
- 위험: 인증 또는 백엔드 데이터 부재로 Summary 화면 캡처가 빈 화면이 될 수 있다.
- 대응: 기존 문서 asset을 먼저 public 경로에 복사하고, 새 캡처가 불가능하면 명확히 보고한다.

## 진행 기록
- 2026-07-09: HTML 이미지 참조가 public 하위 폴더를 필요로 하는 것을 확인했다.
- 2026-07-09: `apps/web/public/l3-spider/l3-spider-guide-assets/`에 설명서 참조 이미지 5개를 배치했다.
- 2026-07-09: Playwright Chromium 실행을 위해 NSS/NSPR 라이브러리를 `/tmp`에 내려받아 사용했고, Dummy ADFS 로그인 후 현재 Summary 화면을 새로 캡처했다.
- 2026-07-09: 새 Summary 캡처를 public asset과 `docs/examples/l3-spider-guide-assets/summary-overview.png`에 반영했다.
- 2026-07-09: 새 Summary 캡처에 1~7번 포인터를 추가하고, 현재 화면에 맞춰 4번/6번 설명 문구를 정리했다.
- 2026-07-09: 이미지 URL 200 응답, `npm run agent:audit:ui`, `npm run web:lint`, `npm run web:build`, `git diff --check` 통과를 확인했다.
- 2026-07-09: Summary 포인터를 다른 설명서 캡처와 같은 빨간 outline/원형 번호 스타일로 재적용했다.
