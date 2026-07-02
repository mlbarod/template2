"""L3 Spider 더미 Parquet 데이터를 생성합니다.

기본 출력 경로:
  data/l3_spider/daily_anomaly/{date}/{line_id}/{process_id}/{eds_step}/{step_seq}#{ppid}#{index}

파일명은 실제 raw data 계약처럼 .parquet 확장자 없이 생성합니다.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_ROOT = Path(__file__).resolve().parent / "data" / "l3_spider" / "daily_anomaly"
DEFAULT_DATES = ["2026-06-17", "2026-06-18"]

LINE_PROCESS_IDS = {
    "line_a": ["ABCD", "ABCE", "ABCF", "ABCG"],
    "line_b": ["ABCH", "ABCI", "ABCJ", "ABCK", "ABCL"],
    "line_c": ["ABCM", "ABCN", "ABCO", "ABCP", "ABCQ", "ABCR"],
    "line_d": ["ABCS", "ABCT", "ABCU", "ABCV"],
    "line_e": ["ABCW", "ABCX", "ABCY", "ABCZ", "ABDA"],
}
EDS_STEPS = ["eds_001", "eds_002", "eds_003", "eds_004"]
STEP_SEQS = ["step_001", "step_002", "step_003"]
PPIDS = ["ppid_a", "ppid_b", "ppid_c"]
EQP_IDS = ["eqp_301", "eqp_302", "eqp_303"]
CHAMBERS = ["pm1", "pm2"]
BIN_NAMES = ["bin_profile", "bin_cd_shift", "bin_edge_loss"]
STATUSES = ["Normal (Ref)", "Normal (Ref)", "Normal (Ref)", "Warning", "High Risk Chamber"]

ROWS_PER_STEP_PPID = 24
RNG = np.random.default_rng(20260619)


def _parse_args() -> argparse.Namespace:
    """CLI 인자를 파싱합니다."""

    parser = argparse.ArgumentParser(description="L3 Spider 더미 데이터를 생성합니다.")
    parser.add_argument(
        "--root",
        default=str(DEFAULT_ROOT),
        help=f"출력 루트 경로 (기본: {DEFAULT_ROOT})",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="생성 대상 파일명 패턴(step#ppid#index)만 먼저 삭제합니다.",
    )
    return parser.parse_args()


def _safe_unlink_generated_files(root: Path) -> int:
    """기존 생성 파일 중 step#ppid#index 패턴을 삭제하고 빈 디렉터리를 정리합니다."""

    if not root.exists():
        return 0

    removed = 0
    for path in root.rglob("*#*#*"):
        if path.is_file() and len(path.name.split("#")) == 3:
            path.unlink()
            removed += 1

    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.is_dir():
            try:
                path.rmdir()
            except OSError:
                pass
    return removed


def _make_rows(
    *,
    date: str,
    line_id: str,
    process_id: str,
    eds_step: str,
    step_seq: str,
    ppid: str,
) -> list[dict[str, object]]:
    """하나의 step_seq/ppid 조합에 대한 더미 row를 생성합니다."""

    base_time = pd.Timestamp(f"{date} 08:00:00")
    rows: list[dict[str, object]] = []
    for index in range(ROWS_PER_STEP_PPID):
        eqp_id = str(RNG.choice(EQP_IDS))
        chamber = str(RNG.choice(CHAMBERS))
        eqc = f"{eqp_id}_{chamber}"
        bin_name = str(RNG.choice(BIN_NAMES))
        status = str(RNG.choice(STATUSES))
        q1 = float(RNG.uniform(0.7, 1.5))
        q3 = float(RNG.uniform(2.0, 3.2))
        lsl = 0.0
        usl = 4.0
        bin_value = float(RNG.normal(2.0, 0.65))
        if status == "High Risk Chamber":
            bin_value = float(RNG.uniform(4.2, 5.8))
        elif status == "Warning":
            bin_value = float(RNG.uniform(3.5, 4.4))

        tkin_time = base_time + pd.Timedelta(minutes=30 * index)
        rows.append(
            {
                "tkin_time": tkin_time,
                "tkout_time": tkin_time + pd.Timedelta(minutes=20),
                "owning": line_id,
                "step_seq": step_seq,
                "ppid": ppid,
                "root_lot_id": f"root_{date.replace('-', '')}_{index // 6:02d}",
                "lot_id": f"lot_{process_id}_{index // 3:03d}",
                "wafer_id": f"{(index % 25) + 1:02d}",
                "eqp_id": eqp_id,
                "chamber_id": chamber,
                "eqc": eqc,
                "bin_name": bin_name,
                "bin_value": bin_value,
                "prop_over_50": float(RNG.uniform(0.0, 1.0)),
                "q1": q1,
                "q3": q3,
                "iqr": q3 - q1,
                "lsl": lsl,
                "usl": usl,
                "seq_idx": index,
                "risk_score": float(RNG.uniform(0.0, 1.0)),
                "display_status": status,
                "comment": "더미 이상감지" if status != "Normal (Ref)" else None,
            }
        )
    return rows


def main() -> None:
    """더미 데이터를 생성합니다."""

    args = _parse_args()
    root = Path(args.root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    if args.clean:
        removed = _safe_unlink_generated_files(root)
        print(f"기존 생성 파일 삭제: {removed}개")

    file_count = 0
    row_count = 0
    for date in DEFAULT_DATES:
        for line_id, process_ids in LINE_PROCESS_IDS.items():
            for process_id in process_ids:
                for eds_step in EDS_STEPS:
                    target_dir = root / date / line_id / process_id / eds_step
                    target_dir.mkdir(parents=True, exist_ok=True)
                    for step_seq in STEP_SEQS:
                        for ppid_index, ppid in enumerate(PPIDS):
                            rows = _make_rows(
                                date=date,
                                line_id=line_id,
                                process_id=process_id,
                                eds_step=eds_step,
                                step_seq=step_seq,
                                ppid=ppid,
                            )
                            output_path = target_dir / f"{step_seq}#{ppid}#{ppid_index}"
                            pd.DataFrame(rows).to_parquet(output_path, engine="pyarrow", index=False)
                            file_count += 1
                            row_count += len(rows)

    print(f"출력 경로: {root}")
    print(f"생성 완료: 파일 {file_count}개, row {row_count}개")


if __name__ == "__main__":
    main()
