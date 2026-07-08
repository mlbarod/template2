# PM SPIDER 대시보드 데이터 연동 명세

## 1. 서버별 BASE 경로

| 환경 | BASE_DATA | BASE_RESULT |
|------|-----------|-------------|
| 로컬/컨테이너 | `/data/pm_spider/data/` | `/data/pm_spider/result/` |
| 호스트 기본값 | `../data/pm_spider/data/` | `../data/pm_spider/result/` |

> BASE 이후 하위 경로 구조는 양쪽 동일. BASE만 환경에 맞게 설정.

---

## 2. 디렉토리 구조 전체

```
BASE_RESULT/
├── score_data/                          ← 스코어/랭킹 (대시보드 주 입력)
│   └── line_id={LINE_ID}/
│       └── eqp_id={EQP_ID}/
│           └── chamber_id={CHAMBER_ID}/
│               └── type={TYPE}/
│                   ├── data_type=trace/
│                   │   └── scores.parquet
│                   └── data_type=oes/
│                       └── scores.parquet
│
└── decomp_data/                         ← Shape/Jitter 신호 시각화용
    └── line_id={LINE_ID}/
        └── eqp_id={EQP_ID}/
            └── chamber_id={CHAMBER_ID}/
                └── type={TYPE}/
                    └── comp_dt={YYYY-MM-DD}/
                        └── param={PARAM}/
                            └── ch_step={CH_STEP}/
                                ├── shape.parquet
                                └── jitter.parquet

BASE_DATA/
└── {LINE_ID}/{EQP_ID}/{CHAMBER_ID}/
    └── {PM_START}/                      ← 예: "2026-05-29 00:00:00"
        ├── trace/
        │   └── type={TYPE}/
        │       └── ppid={PPID}/
        │           └── recipe_id={RECIPE_ID}/
        │               └── priority={PRIORITY}/
        │                   └── trace_param_name={PARAM}/
        │                       └── *.parquet
        └── oes/
            └── {TYPE}/
                └── {STEP_SEQ}/
                    └── {PPID}/
                        └── {RECIPE_ID}/
                            └── {LOT_ID}/
                                └── {SLOT_NO}/
                                    └── {file_name}.parquet
```

---

## 3. 파티션 키 정의

| 키 | 예시 | 허용값 |
|----|------|--------|
| LINE_ID | `ABCD` | 영문·숫자·_·- |
| EQP_ID | `ABCD801` | 영문·숫자·_·- |
| CHAMBER_ID | `PM2` | 영문·숫자·_·- |
| TYPE | `ag` / `process` | ag=NPW seasoning, process=PW |
| PARAM | `RF_POWER` | `V_` 로 시작하는 항목 제외 |
| CH_STEP | `3` / `5` / `6` | 0, -1~-5 제외 |
| COMP_DT | `2026-05-29` | YYYY-MM-DD |
| PRIORITY | `1` | |

---

## 4. 파일별 스키마

### 4-1. score_data/trace/scores.parquet

| 컬럼 | 타입 | 설명 |
|------|------|------|
| 날짜 | str | comp PM 날짜 (YYYY-MM-DD) |
| ref_dates | str | JSON 배열 `["2026-03-10","2026-04-21"]` |
| item_name | str | trace_param_name (예: RF_POWER) |
| score | float | 0~1, **낮을수록 나쁨** |
| step | str | ch_step |
| delta_shape | float | P3 ΔShape |
| delta_jitter | float | P3 ΔJitter |
| delta_level | float | P3 ΔLevel (참고용) |
| flag | str | `OK` / `SHAPE` / `JITTER` / `SHAPE+JITTER` |
| alarm_pct | float | P2 ALARM wafer 비율 (%) |
| line_id | str | |
| eqp_id | str | |
| chamber_id | str | |
| type | str | ag / process |
| data_type | str | trace |

### 4-2. score_data/oes/scores.parquet

| 컬럼 | 타입 | 설명 |
|------|------|------|
| 날짜 | str | comp PM 날짜 |
| ref_dates | str | JSON 배열 |
| item_name | str | rcp_step (예: 1D) |
| score | float | 0~1, 낮을수록 나쁨 |
| step | str | rcp_step |
| wavelength | float | nm |
| delta_spectrum | float | P3 ΔSpectrum |
| direction | str | UP / DOWN |
| flagged_wl | int | 유의차 파장 수 |
| line_id, eqp_id, chamber_id, type, data_type | str | 파티션 식별 |

### 4-3. decomp_data/.../shape.parquet

| 컬럼 | 타입 | 설명 |
|------|------|------|
| 날짜 | str | comp PM 날짜 |
| ref_dates | str | JSON 배열 |
| phase | int | 0~99 |
| value | float | shape 값 (Level 제거됨, 0 근처) |
| group | str | `ref_{lot}_{slot}` / `comp_{lot}_{slot}` / `tube_q50` / `tube_usl` / `tube_lsl` |
| lot_id | str | tube 계열은 `""` |
| slot_no | int | tube 계열은 `-1` |

### 4-4. decomp_data/.../jitter.parquet

| 컬럼 | 타입 | 설명 |
|------|------|------|
| 날짜 | str | comp PM 날짜 |
| ref_dates | str | JSON 배열 |
| lot_id | str | |
| slot_no | int | |
| jitter_rms | float | RMS noise 수준 |
| level | float | baseline (참고용) |
| group | str | `ref` / `comp` |

### 4-5. trace raw (참고용, 대시보드 직접 읽을 경우)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| Time | Float32 | 시간 (s) |
| value | Float32 | 센서값 |
| ch_step | str | |
| lot_id | str | |
| slot_no | int | |
| eqp_id | str | |
| fdc_bin | str | |

### 4-6. OES raw 파일명 규칙

파일명을 `#` 으로 split:
```
{line_id}#{process_id}#{step_seq}#{rcp_step}#{ppid}#{recipe_id}
#{eqp_id}#{chamber_id}#{lot_id}#{slot_no}#{wafer_end_time}.parquet
```

OES raw 스키마:
```
Time: Float32
'200.0', '200.5', ..., '800.0': Float32   (파장 컬럼, 0.5nm 간격, 1201개)
```

---

## 5. score 값 규칙

```
score = 1 / (1 + delta)   →  0~1 범위, 낮을수록 나쁨 (rank 1 = worst)

delta=0   →  score=1.00  (변화 없음)
delta=1   →  score=0.50  (flag 경계)
delta=2   →  score=0.33
delta=5   →  score=0.17  (심각)
```

---

## 6. ref_dates 처리 방법

```python
import json

# 저장 형식
ref_dates = '["2026-03-10","2026-04-21"]'  # JSON string

# 읽을 때
dates = json.loads(ref_dates)  # → ["2026-03-10", "2026-04-21"]

# 빈 경우 (첫 번째 PM)
ref_dates = '[]'
```

---

## 7. shape.parquet group 컬럼 활용

```python
import polars as pl

df = pl.read_parquet("shape.parquet")

# ref wafer 개별 신호
ref_wafers = df.filter(pl.col("group").str.starts_with("ref_"))

# comp wafer 개별 신호
comp_wafers = df.filter(pl.col("group").str.starts_with("comp_"))

# ref tube 중심선
q50 = df.filter(pl.col("group") == "tube_q50")

# ref tube 상단/하단
usl = df.filter(pl.col("group") == "tube_usl")
lsl = df.filter(pl.col("group") == "tube_lsl")
```

---

## 8. 대시보드 selectors.py 구현 가이드

```python
BASE_RESULT = "/data/pm_spider/result"  # api 컨테이너 내부 경로

# score_data 읽기
def get_score_path(line_id, eqp_id, chamber_id, type_, data_type):
    return (f"{BASE_RESULT}/score_data"
            f"/line_id={line_id}/eqp_id={eqp_id}/chamber_id={chamber_id}"
            f"/type={type_}/data_type={data_type}/scores.parquet")

# decomp_data 읽기
def get_shape_path(line_id, eqp_id, chamber_id, type_, comp_dt, param, ch_step):
    return (f"{BASE_RESULT}/decomp_data"
            f"/line_id={line_id}/eqp_id={eqp_id}/chamber_id={chamber_id}"
            f"/type={type_}/comp_dt={comp_dt}/param={param}/ch_step={ch_step}"
            f"/shape.parquet")

def get_jitter_path(line_id, eqp_id, chamber_id, type_, comp_dt, param, ch_step):
    return (f"{BASE_RESULT}/decomp_data"
            f"/line_id={line_id}/eqp_id={eqp_id}/chamber_id={chamber_id}"
            f"/type={type_}/comp_dt={comp_dt}/param={param}/ch_step={ch_step}"
            f"/jitter.parquet")
```

---

## 9. 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-06-13 | 최초 작성 |
| 2026-06-13 | pattern→type, NPW→ag, PW→process |
| 2026-06-13 | chamber_id 파티션 추가 |
| 2026-06-13 | ref_dates JSON 컬럼 추가 (복수 ref 지원) |
| 2026-06-15 | decomp_data (shape/jitter) 추가 |
| 2026-06-15 | 테스트/대시보드 서버 BASE 경로 명시 |
