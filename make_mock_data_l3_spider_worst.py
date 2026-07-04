"""L3 Spider worst-case 더미 Parquet 데이터를 생성합니다 (차트 스크롤 성능 테스트용).

출력 경로:
  data/l3_spider/daily_anomaly/{date}/{line_id}/{process_id}/{eds_step}/{step_seq}#{ppid}#{index}

worst 조건 (차트는 드릴한 leaf로 필터됨을 반영):
  - EQPCH 30개 (eqp 10 × chamber 3), bin 3종, 파일당 27,000행
  - Bin 선택 시 → EQPCH-trellis: subplot 30개 × 각 ~300행(= 한 bin 9,000행을 30 eqc로 분할)
    → 스크롤 부하(subplot 30개)의 최악 케이스. 사용자 예시(25 eqpch × 200)를 상회.
  - EQPCH 선택 시 → bin-trellis: subplot 3개(해당 eqc의 bin들)

기존 make_mock_data_l3_spider.py 와 달리 numpy 벡터화로 대량 행을 빠르게 생성합니다.
2026-06-17/18 등 다른 날짜는 건드리지 않습니다.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_ROOT = Path(__file__).resolve().parent / "data" / "l3_spider" / "daily_anomaly"
DATE = "2026-06-20"

# 구조(파일 수를 낮게 유지해 파일당 대용량을 감당) — 그래도 라인/매트릭스는 브라우징 가능
LINE_PROCESS_IDS = {
    "line_a": ["ABCD", "ABCE"],
    "line_b": ["ABCH", "ABCI"],
    "line_c": ["ABCM", "ABCN"],
}
EDS_STEPS = ["eds_001", "eds_002"]
STEP_SEQS = ["step_001", "step_002"]
PPIDS = ["ppid_a", "ppid_b"]

N_EQP = 10          # eqp_301 .. eqp_310
N_CHAMBER = 3       # pm1, pm2, pm3  → EQPCH 30개
N_BIN = 3           # bin_01 .. bin_03 (적게 두어 bin-드릴 시 EQPCH subplot 밀도↑)
ROWS_PER_FILE = 27000   # bin 드릴 시 한 bin 9,000행 → 30 EQPCH subplot × ~300행

EQP_IDS = np.array([f"eqp_{301 + i}" for i in range(N_EQP)])
CHAMBERS = np.array([f"pm{i + 1}" for i in range(N_CHAMBER)])
BIN_NAMES = np.array([f"bin_{i + 1:02d}" for i in range(N_BIN)])
STATUSES = np.array(["Normal (Ref)", "Warning", "High Risk Chamber"])
STATUS_P = [0.80, 0.13, 0.07]


def _make_frame(*, date: str, line_id: str, process_id: str, step_seq: str, ppid: str, rng: np.random.Generator) -> pd.DataFrame:
    """벡터화로 한 파일 분량(ROWS_PER_FILE)의 행을 생성합니다."""
    n = ROWS_PER_FILE

    # EQPCH를 균등 배분(각 ~900행) 후 셔플
    eqc_idx = np.tile(np.arange(N_EQP * N_CHAMBER), n // (N_EQP * N_CHAMBER) + 1)[:n]
    rng.shuffle(eqc_idx)
    eqp_id = EQP_IDS[eqc_idx // N_CHAMBER]
    chamber = CHAMBERS[eqc_idx % N_CHAMBER]
    eqc = np.char.add(np.char.add(eqp_id, "_"), chamber)

    bin_name = BIN_NAMES[rng.integers(0, N_BIN, n)]
    status_idx = rng.choice(3, size=n, p=STATUS_P)
    display_status = STATUSES[status_idx]

    bin_value = rng.normal(2.0, 0.65, n)
    bin_value = np.where(status_idx == 2, rng.uniform(4.2, 5.8, n), bin_value)
    bin_value = np.where(status_idx == 1, rng.uniform(3.5, 4.4, n), bin_value)

    q1 = rng.uniform(0.7, 1.5, n)
    q3 = rng.uniform(2.0, 3.2, n)

    base = pd.Timestamp(f"{date} 08:00:00")
    tkin = base + pd.to_timedelta(rng.integers(0, 12 * 60, n), unit="m")
    idx = np.arange(n)

    return pd.DataFrame({
        "tkin_time": tkin,
        "tkout_time": tkin + pd.Timedelta(minutes=20),
        "owning": line_id,
        "step_seq": step_seq,
        "ppid": ppid,
        "root_lot_id": np.char.add(f"root_{date.replace('-', '')}_", np.char.zfill((idx // 200).astype(str), 3)),
        "lot_id": np.char.add(f"lot_{process_id}_", np.char.zfill((idx // 25).astype(str), 4)),
        "wafer_id": np.char.zfill((idx % 25 + 1).astype(str), 2),
        "eqp_id": eqp_id,
        "chamber_id": chamber,
        "eqc": eqc,
        "bin_name": bin_name,
        "bin_value": bin_value,
        "prop_over_50": rng.uniform(0.0, 1.0, n),
        "q1": q1,
        "q3": q3,
        "iqr": q3 - q1,
        "lsl": np.zeros(n),
        "usl": np.full(n, 4.0),
        "seq_idx": idx,
        "risk_score": rng.uniform(0.0, 1.0, n),
        "display_status": display_status,
        "comment": np.where(status_idx == 0, None, "더미 이상감지"),
    })


def main() -> None:
    parser = argparse.ArgumentParser(description="L3 Spider worst-case 더미 데이터 생성")
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    date_root = root / DATE
    if date_root.exists():
        shutil.rmtree(date_root)  # 06-20만 재생성
    rng = np.random.default_rng(20260620)

    files = 0
    rows = 0
    for line_id, process_ids in LINE_PROCESS_IDS.items():
        for process_id in process_ids:
            for eds_step in EDS_STEPS:
                target = date_root / line_id / process_id / eds_step
                target.mkdir(parents=True, exist_ok=True)
                for step_seq in STEP_SEQS:
                    for ppid_index, ppid in enumerate(PPIDS):
                        df = _make_frame(
                            date=DATE, line_id=line_id, process_id=process_id,
                            step_seq=step_seq, ppid=ppid, rng=rng,
                        )
                        df.to_parquet(target / f"{step_seq}#{ppid}#{ppid_index}", engine="pyarrow", index=False)
                        files += 1
                        rows += len(df)

    print(f"[worst] {DATE} 생성: 파일 {files}개, row {rows:,}개 (파일당 {ROWS_PER_FILE:,}, EQPCH {N_EQP*N_CHAMBER}, bin {N_BIN})")
    print(f"출력: {date_root}")


if __name__ == "__main__":
    main()
