"""
make_pm_spider_result_mock.py — PM SPIDER 결과 모의 데이터 생성
score_data와 decomp_data 구조를 생성합니다.

실행:
  python make_pm_spider_result_mock.py
"""
from pathlib import Path
import numpy as np
import pandas as pd
import json

np.random.seed(42)

# ── 설정 ──────────────────────────────────────────────────────
LINE_ID    = "PFAA"
EQP_ID     = "EAAA301"
CHAMBER_ID = "PM2"
PPID       = "PPID001"
RECIPE_ID  = "RCP001"
TYPES      = ["ag", "process"]

# 호스트 경로 (docker mount: data/pm_spider → /data/pm_spider)
BASE_RESULT = Path(__file__).parent / "data" / "pm_spider" / "result"

# 3개 PM cycle (trend 테스트용)
PM_DATES = ["2026-03-10", "2026-04-21", "2026-05-29"]

# ref_dates 매핑 (각 PM의 ref로 사용된 이전 사이클)
REF_DATES_MAP = {
    "2026-03-10": [],
    "2026-04-21": ["2026-03-10"],
    "2026-05-29": ["2026-03-10", "2026-04-21"],
}

PARAMS    = ["RF_POWER", "RF_REFLECT", "PRESSURE",
             "GAS_FLOW_AR", "GAS_FLOW_C4F8", "GAS_FLOW_O2",
             "DC_BIAS", "ESC_TEMP", "WALL_TEMP", "MATCH_C1", "MATCH_C2"]
CH_STEPS  = ["3", "5", "6", "8"]
RCP_STEPS = ["1D", "3D", "4D", "5D", "6D"]
WLS       = np.arange(200.0, 800.5, 5.0).round(1)  # 121개
N_PHASE   = 100
LOTS      = ["LOT001", "LOT002"]
SLOTS     = list(range(1, 7))  # 6장


# ── 헬퍼 ──────────────────────────────────────────────────────
def mkd(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p

def score(delta: float) -> float:
    """score = 1 / (1 + delta)  낮을수록 나쁨"""
    return round(1.0 / (1.0 + delta), 6)

def ref_dates_json(date: str) -> str:
    return json.dumps(REF_DATES_MAP.get(date, []))

def save(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False, engine="pyarrow")
    print(f"  저장: result/{path.relative_to(BASE_RESULT)}  ({len(df):,}행)")
    return path


# ══════════════════════════════════════════════════════════════
#  1. score_data/trace
# ══════════════════════════════════════════════════════════════
def make_trace_scores(date: str, cycle_idx: int, type_val: str) -> pd.DataFrame:
    rows = []
    for param in PARAMS:
        for ch_step in CH_STEPS:
            ds = abs(np.random.normal(0.1, 0.08))
            dj = abs(np.random.normal(0.8, 0.3))
            ap = abs(np.random.normal(2.0, 2.0))

            if cycle_idx == 1:
                if param == "RF_POWER" and ch_step == "5":
                    ds = abs(np.random.normal(2.3, 0.4))
                    ap = abs(np.random.normal(35, 8))
                if param == "RF_REFLECT" and ch_step == "5":
                    ds = abs(np.random.normal(1.7, 0.3))

            if cycle_idx == 2:
                if param == "RF_POWER" and ch_step in ["5","6"]:
                    ds = abs(np.random.normal(3.1, 0.5))
                    ap = abs(np.random.normal(55, 10))
                if param == "PRESSURE":
                    dj = abs(np.random.normal(3.5, 0.6))
                    ap = abs(np.random.normal(25, 8))
                if param == "DC_BIAS" and ch_step == "5":
                    ds = abs(np.random.normal(1.8, 0.3))

            flag = ""
            if ds >= 1.5: flag += "SHAPE"
            if dj >= 1.5: flag += ("+JITTER" if flag else "JITTER")
            if not flag:  flag = "OK"

            rows.append({
                "날짜":         date,
                "ref_dates":   ref_dates_json(date),
                "item_name":   param,
                "score":       score(ds),
                "step":        ch_step,
                "delta_shape":  round(ds, 4),
                "delta_jitter": round(dj, 4),
                "delta_level":  round(np.random.normal(0, 0.3), 4),
                "flag":         flag,
                "alarm_pct":    round(min(ap, 100), 1),
                "line_id":     LINE_ID,
                "eqp_id":      EQP_ID,
                "chamber_id":  CHAMBER_ID,
                "type":        type_val,
                "data_type":   "trace",
            })
    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════
#  2. score_data/oes
# ══════════════════════════════════════════════════════════════
def make_oes_scores(date: str, cycle_idx: int, type_val: str) -> pd.DataFrame:
    rows = []
    for rcp in RCP_STEPS:
        n_flagged = 0
        for wl in WLS:
            ds = abs(np.random.normal(0.05, 0.03))
            if cycle_idx >= 1:
                if rcp == "1D" and 740 <= wl <= 760:
                    ds = abs(np.random.normal(3.2, 0.5))
                if rcp == "1D" and 770 <= wl <= 785:
                    ds = abs(np.random.normal(2.8, 0.4))
            if cycle_idx == 2:
                if rcp == "4D" and 480 <= wl <= 500:
                    ds = abs(np.random.normal(2.1, 0.4))
                if rcp == "6D" and 650 <= wl <= 670:
                    ds = abs(np.random.normal(1.6, 0.3))
            if ds >= 1.0:
                n_flagged += 1
            rows.append({
                "날짜":           date,
                "ref_dates":     ref_dates_json(date),
                "item_name":     rcp,
                "score":         score(ds),
                "step":          rcp,
                "wavelength":    float(wl),
                "delta_spectrum": round(ds, 4),
                "direction":     "UP" if np.random.random() > 0.35 else "DOWN",
                "flagged_wl":    0,
                "line_id":       LINE_ID,
                "eqp_id":        EQP_ID,
                "chamber_id":    CHAMBER_ID,
                "type":          type_val,
                "data_type":     "oes",
            })
        for r in rows[-len(WLS):]:
            r["flagged_wl"] = n_flagged
    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════
#  3. decomp_data/shape + jitter
# ══════════════════════════════════════════════════════════════
def base_shape(p: int, param: str) -> float:
    """가상 shape 기준값"""
    level = {"RF_POWER": 100.0, "PRESSURE": 50.0}.get(param, 80.0)
    t = p / 99 * 10
    ramp = 2.0
    sig = (level * (1 - np.exp(-3 * t / ramp)) if t < ramp
           else level * (1 + 0.04 * np.sin(np.pi * (t - ramp) / 8)))
    return sig - level  # level 제거


def make_decomp(date: str, cycle_idx: int, type_val: str):
    """shape.parquet + jitter.parquet 생성"""
    ph = list(range(N_PHASE))

    targets = []
    for param in PARAMS:  # 전체 파라미터
        for ch_step in CH_STEPS:
            targets.append((param, ch_step))

    for param, ch_step in targets:
        # ── shape ──────────────────────────────────────────
        shape_rows = []

        ref_shapes = []
        for slot in SLOTS:
            lot = LOTS[slot % len(LOTS)]
            noise = 0.5
            shape_vals = [base_shape(p, param) + np.random.normal(0, noise)
                          for p in ph]
            ref_shapes.append(shape_vals)
            shape_rows.append(pd.DataFrame({
                "날짜":      date,
                "ref_dates": ref_dates_json(date),
                "phase":     ph,
                "value":     [round(v, 4) for v in shape_vals],
                "group":     f"ref_{lot}_{slot}",
                "lot_id":    lot,
                "slot_no":   slot,
            }))

        # comp
        for slot in SLOTS:
            lot = LOTS[slot % len(LOTS)]
            shift = 0.0
            if cycle_idx >= 1 and param == "RF_POWER" and ch_step == "5":
                shift = 2.5
            if cycle_idx == 2 and param == "PRESSURE":
                shift = 1.2
            shape_vals = [base_shape(p, param) + shift
                          + np.random.normal(0, 0.6) for p in ph]
            shape_rows.append(pd.DataFrame({
                "날짜":      date,
                "ref_dates": ref_dates_json(date),
                "phase":     ph,
                "value":     [round(v, 4) for v in shape_vals],
                "group":     f"comp_{lot}_{slot}",
                "lot_id":    lot,
                "slot_no":   slot,
            }))

        # tube (ref 기준)
        mat  = np.array(ref_shapes)
        q50  = np.median(mat, axis=0)
        mad  = np.median(np.abs(mat - q50), axis=0) * 1.4826
        mad  = np.maximum(mad, 0.01)
        for gname, vals in [
            ("tube_q50", q50),
            ("tube_usl", q50 + 3 * mad),
            ("tube_lsl", q50 - 3 * mad),
        ]:
            shape_rows.append(pd.DataFrame({
                "날짜":      date,
                "ref_dates": ref_dates_json(date),
                "phase":     ph,
                "value":     [round(v, 4) for v in vals.tolist()],
                "group":     gname,
                "lot_id":    "",
                "slot_no":   -1,
            }))

        dest = (BASE_RESULT / "decomp_data"
                / f"line_id={LINE_ID}" / f"eqp_id={EQP_ID}"
                / f"chamber_id={CHAMBER_ID}" / f"type={type_val}"
                / f"comp_dt={date}" / f"param={param}"
                / f"ch_step={ch_step}")
        save(pd.concat(shape_rows, ignore_index=True), dest / "shape.parquet")

        # ── jitter ─────────────────────────────────────────
        jitter_rows = []
        for grp, slots in [("ref", SLOTS), ("comp", SLOTS)]:
            for slot in slots:
                lot = LOTS[slot % len(LOTS)]
                base_j = 1.3
                if grp == "comp" and cycle_idx == 2 and param == "PRESSURE":
                    base_j = 3.5
                jitter_rows.append({
                    "날짜":       date,
                    "ref_dates":  ref_dates_json(date),
                    "lot_id":     lot,
                    "slot_no":    slot,
                    "jitter_rms": round(abs(np.random.normal(base_j, 0.2)), 4),
                    "level":      round({"RF_POWER":100.0,"PRESSURE":50.0}.get(param,80.0), 2),
                    "group":      grp,
                })
        save(pd.DataFrame(jitter_rows), dest / "jitter.parquet")


# ══════════════════════════════════════════════════════════════
#  main
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=== 대시보드 mock 데이터 생성 ===")
    print(f"BASE_RESULT: {BASE_RESULT}\n")

    for type_val in TYPES:
        print(f"\n{'='*50}")
        print(f"TYPE: {type_val} ({'NPW/ag' if type_val == 'ag' else 'PW/process'})")
        trace_frames, oes_frames = [], []
        for i, date in enumerate(PM_DATES):
            print(f"\n[PM cycle {i+1}] {date}")
            trace_frames.append(make_trace_scores(date, i, type_val))
            oes_frames.append(make_oes_scores(date, i, type_val))
            make_decomp(date, i, type_val)

        # score 저장 (모든 cycle 합산)
        print(f"\n[score_data 저장 — type={type_val}]")
        trace_all = pd.concat(trace_frames, ignore_index=True)
        oes_all   = pd.concat(oes_frames,   ignore_index=True)

        score_base = (BASE_RESULT / "score_data"
                      / f"line_id={LINE_ID}" / f"eqp_id={EQP_ID}"
                      / f"chamber_id={CHAMBER_ID}" / f"type={type_val}")
        save(trace_all, score_base / "data_type=trace" / "scores.parquet")
        save(oes_all,   score_base / "data_type=oes"   / "scores.parquet")

    print("\n=== 완료 ===")
    print(f"\n생성 파일:")
    import glob
    for f in sorted(glob.glob(str(BASE_RESULT / "**/*.parquet"), recursive=True)):
        p = Path(f)
        sz = p.stat().st_size / 1024
        print(f"  {p.relative_to(BASE_RESULT)}  ({sz:.1f}KB)")
