# ExecPlan: branch merge routine

## 목표
- 특정 `y5` 브랜치 전용 병합 루틴을 임의 source branch에 사용할 수 있는 범용 병합 루틴으로 변경한다.
- source branch 변경 의도를 존중하되 다른 feature/app/API/public facade 훼손 여부를 확인하도록 유지한다.

## 현재 상태
- `.codex/skills/branch-merge-routine`이 새 skill로 생성되어 있다.
- `AGENTS.md`에는 `Branch merge routine` 라우팅이 추가되어 있다.
- `apps/web/src/features/observer/*`에 이 요청과 무관한 미커밋 변경이 있으며 건드리지 않는다.

## 범위
- 수정: `AGENTS.md`, `.codex/skills/branch-merge-routine/*`의 범용 이름/본문/메타데이터
- 생성/이동: `.codex/skills/branch-merge-routine/*`
- 제외: observer feature 변경, 실제 Git branch merge/push 동작

## 설계
- skill 이름은 `branch-merge-routine`으로 한다.
- 본문은 `<source_branch>`와 `<target_branch>`를 사용하되 기본 target은 `main`으로 둔다.
- `y5`는 trigger 예시로만 남긴다.
- API, DB, auth, env contract 변경은 없다.

## 실행 단계
- [x] skill 디렉터리를 `branch-merge-routine`으로 변경한다.
- [x] `SKILL.md`의 frontmatter, 제목, 명령 예시를 범용 브랜치 기준으로 바꾼다.
- [x] `agents/openai.yaml` 표시 메타데이터를 갱신한다.
- [x] `AGENTS.md` 라우팅을 `Branch merge routine`으로 바꾼다.
- [x] skill validator와 placeholder 검색을 실행한다.

## 검증
- `python3 /home/pjw75/.codex/skills/.system/skill-creator/scripts/quick_validate.py .codex/skills/branch-merge-routine`
- skill/라우팅 파일에 placeholder와 이전 skill 경로가 남지 않았는지 검색한다.
- `git status --short --branch`

## 위험과 대응
- 위험: `y5` 전용 trigger가 사라져 기존 요청이 덜 잘 매칭될 수 있다.
- 대응: description과 default prompt에 `y5` 요청 예시를 유지한다.

## 진행 기록
- 2026-07-07: y5 전용 루틴을 범용 branch merge routine으로 전환하기로 결정했다.
- 2026-07-07: skill 폴더와 라우팅을 `branch-merge-routine`으로 변경했다.
- 2026-07-07: skill validator가 통과했고 이전 skill 경로가 남지 않았음을 확인했다.
