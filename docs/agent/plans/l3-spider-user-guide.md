# ExecPlan: L3 Spider 사용자 설명서

## 목표
- L3 Spider 실제 Web 화면을 캡처해 `docs/examples` 아래에 한국어 설명서를 만든다.
- 각 캡처에는 번호 포인터를 붙이고, 설명서에서 각 영역의 역할과 읽는 방법을 설명한다.

## 현재 상태
- L3 Spider Web route는 `/l3_spider`이다.
- 화면은 Summary 탭, Chart 탭, 상세 필터, 메일 규칙 설정, 제외 필터 설정으로 구성된다.
- 기존 API 문서는 `docs/api/l3-spider.md`에 있으나 사용자용 화면 설명서는 별도로 없다.

## 범위
- 추가: `docs/examples/l3-spider-user-guide.md`
- 추가: `docs/examples/l3-spider-*.png` 캡처/주석 이미지
- 제외: L3 Spider frontend/backend 동작 변경, API 계약 변경, 운영 데이터 경로 변경

## 설계
- 캡처는 로컬 dev 환경의 실제 `/l3_spider` 페이지에서 생성한다.
- 설명서는 운영 URL이나 사내망 주소를 하드코딩하지 않고, 화면 사용법과 지표 해석에 집중한다.
- 이미지 포인터는 문서 본문과 같은 번호를 사용한다.

## 실행 단계
- [x] ExecPlan 작성
- [x] L3 Spider 화면 구조와 실행 방법 확인
- [x] 로컬 앱 실행 및 실제 화면 캡처
- [x] 캡처 이미지에 번호 포인터 추가
- [x] `docs/examples`에 설명서 작성
- [x] 문서 링크와 산출물 검증

## 검증
- `test -f docs/examples/l3-spider-user-guide.md`
- `find docs/examples -maxdepth 1 -name 'l3-spider-*.png' | sort`
- `npm run agent:audit:docs`

## 위험과 대응
- 위험: 로컬 데이터나 API가 준비되지 않으면 실제 대시보드가 빈 화면으로 캡처될 수 있다.
- 대응: 저장소의 mock data와 dev compose 상태를 확인하고, 불가하면 확인 가능한 실제 UI 상태와 제한 사항을 문서에 명시한다.

## 진행 기록
- 2026-07-03: 설명서 위치를 `docs/examples`로 확정하고 실행 계획을 작성했다.
- 2026-07-03: 로컬 dev `/l3_spider` 실제 화면을 Playwright로 캡처하고 Summary, Chart, 메일 설정, 메일 Rule 폼, 제외 필터 이미지를 생성했다.
- 2026-07-03: `docs/examples/l3-spider-user-guide.md` 설명서를 추가했다.
- 2026-07-03: `docs/inventory.md`의 L3 Spider endpoint 색인에 기존 `daily-summary` 누락을 보완하고 `npm run agent:audit:docs` 통과를 확인했다.
