"""
PM SPIDER raw mock 데이터를 생성합니다.

생성 경로는 PM Comparison selector의 raw partition 계약을 따릅니다.

  data/pm_spider/data/
    line_id=<>/eqp_id=<>/fdc_bin=<>/dt=<YYYY-MM-DD>/type=<ag|process>/
    ppid=<>/recipe_id=<>/data_source=<trace|oes>/trace_param_name=<>/
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


LINE_ID = "PFAA"
EQP_ID = "EAAA301"
FDC_BIN = "PM2"
PPID = "PPID001"
RECIPE_ID = "RCP001"
TYPES = ["ag", "process"]
PM_DATES = ["2026-03-10", "2026-04-21", "2026-05-29"]

TRACE_PARAMS = [
    "RF_POWER",
    "RF_REFLECT",
    "PRESSURE",
    "GAS_FLOW_AR",
    "GAS_FLOW_C4F8",
    "GAS_FLOW_O2",
    "DC_BIAS",
    "ESC_TEMP",
    "WALL_TEMP",
    "MATCH_C1",
    "MATCH_C2",
]
CH_STEPS = ["3", "5", "6", "8"]
RCP_STEPS = ["1D", "3D", "4D", "5D", "6D"]
WAVELENGTHS = np.arange(200.0, 800.0 + 0.5, 0.5).round(1)
LOTS = ["LOT001", "LOT002"]
SLOTS = [1, 2, 3, 4, 5, 6]
OES_SLOTS = list(range(1, 26))
OES_BASE_TIME_POINTS = 398
OES_EXTRA_TIME_SERIES = 44


def parse_args() -> argparse.Namespace:
    """CLI 인자를 파싱합니다."""

    parser = argparse.ArgumentParser(description="PM SPIDER raw mock 데이터 생성기")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).parent / "data" / "pm_spider" / "data",
        help="raw data 루트 경로입니다. 기본값은 ./data/pm_spider/data 입니다.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20260619,
        help="난수 seed 입니다.",
    )
    return parser.parse_args()


def _partition_dir(root: Path, *, date: str, type_value: str, data_source: str, trace_param_name: str) -> Path:
    """raw partition 디렉터리 경로를 반환합니다."""

    return (
        root
        / f"line_id={LINE_ID}"
        / f"eqp_id={EQP_ID}"
        / f"fdc_bin={FDC_BIN}"
        / f"dt={date}"
        / f"type={type_value}"
        / f"ppid={PPID}"
        / f"recipe_id={RECIPE_ID}"
        / f"data_source={data_source}"
        / f"trace_param_name={trace_param_name}"
    )


def _slot_rows() -> Iterable[tuple[str, int, str]]:
    """lot/slot/wafer 조합을 순회합니다."""

    for slot_no in SLOTS:
        lot_id = LOTS[slot_no % len(LOTS)]
        yield lot_id, slot_no, f"{lot_id}_W{slot_no:02d}"


def _oes_slot_rows() -> Iterable[tuple[str, int, str]]:
    """OES용 25매 lot/slot/wafer 조합을 순회합니다."""

    for slot_no in OES_SLOTS:
        lot_id = LOTS[slot_no % len(LOTS)]
        yield lot_id, slot_no, f"{lot_id}_W{slot_no:02d}"


def _trace_base_value(param: str) -> float:
    """센서별 기준값을 반환합니다."""

    values = {
        "RF_POWER": 110.0,
        "RF_REFLECT": 8.0,
        "PRESSURE": 42.0,
        "GAS_FLOW_AR": 140.0,
        "GAS_FLOW_C4F8": 38.0,
        "GAS_FLOW_O2": 18.0,
        "DC_BIAS": -230.0,
        "ESC_TEMP": 24.0,
        "WALL_TEMP": 61.0,
        "MATCH_C1": 52.0,
        "MATCH_C2": 48.0,
    }
    return values.get(param, 50.0)


def make_trace_frame(rng: np.random.Generator, *, date: str, cycle_idx: int, type_value: str, param: str) -> pd.DataFrame:
    """trace raw schema에 맞는 mock frame을 생성합니다."""

    rows: list[dict[str, object]] = []
    base = _trace_base_value(param)
    type_shift = 1.5 if type_value == "process" else 0.0
    cycle_shift = cycle_idx * 1.2
    if param == "RF_POWER" and cycle_idx >= 1:
        cycle_shift += 5.0
    if param == "PRESSURE" and cycle_idx == 2:
        cycle_shift += 3.0

    for lot_id, slot_no, wafer_id in _slot_rows():
        for idx in range(80):
            step_time = round(idx * 0.5, 3)
            ch_step = CH_STEPS[(idx // 20) % len(CH_STEPS)]
            wave = np.sin(idx / 9.0) * 1.8
            noise = rng.normal(0.0, 0.35)
            value = base + type_shift + cycle_shift + wave + noise + slot_no * 0.05
            rows.append(
                {
                    "날짜": date,
                    "time": f"{date}T00:{idx // 60:02d}:{idx % 60:02d}Z",
                    "step_time": step_time,
                    "period": idx,
                    "phase": "comp",
                    "value": round(float(value), 6),
                    "trace_param_name": param,
                    "root_lot_id": lot_id,
                    "lot_id": lot_id,
                    "wafer_id": wafer_id,
                    "ch_step": ch_step,
                    "group": f"comp_{lot_id}_{slot_no}",
                    "slot_no": slot_no,
                }
            )
    return pd.DataFrame(rows)


def _wavelength_column(wavelength: float) -> str:
    """OES wide spectrum 컬럼명을 반환합니다."""

    return f"{float(wavelength):.1f}"


def _oes_intensity_vector(
    rng: np.random.Generator,
    *,
    cycle_idx: int,
    type_value: str,
    rcp_step: str,
    slot_no: int,
    time_idx: int,
    time_count: int,
) -> np.ndarray:
    """OES 0.5nm 해상도 intensity 벡터를 생성합니다."""

    wavelengths = WAVELENGTHS.astype(float)
    type_shift = 12.0 if type_value == "process" else 0.0
    step_offset = RCP_STEPS.index(rcp_step) * 18.0
    time_axis = time_idx / max(time_count - 1, 1)
    time_decay = 1.0 + 0.4 * np.exp(-3.0 * time_axis)
    slot_shift = slot_no * 0.15

    peak_310 = 80.0 * np.exp(-((wavelengths - 310.0) ** 2) / (2 * 30.0**2))
    peak_488 = 120.0 * np.exp(-((wavelengths - 488.0) ** 2) / (2 * 20.0**2))
    peak_750 = 200.0 * np.exp(-((wavelengths - 750.0) ** 2) / (2 * 15.0**2))
    peak_777 = 150.0 * np.exp(-((wavelengths - 777.0) ** 2) / (2 * 12.0**2))
    spectrum = 100.0 + type_shift + step_offset + slot_shift + peak_310 + peak_488 + peak_750 + peak_777

    drift = 1.0 + (cycle_idx * 0.035)
    if cycle_idx >= 1 and rcp_step == "1D":
        spectrum = np.where((740.0 <= wavelengths) & (wavelengths <= 790.0), spectrum * 1.25, spectrum)
    if cycle_idx == 2 and rcp_step == "4D":
        spectrum = np.where((470.0 <= wavelengths) & (wavelengths <= 510.0), spectrum * 0.80, spectrum)

    noise = rng.normal(0.0, 2.0, size=len(wavelengths))
    return (spectrum * time_decay * drift + noise).astype(np.float32)


def _oes_time_points(*, cycle_idx: int, slot_no: int) -> int:
    """실제 OES 규모에 맞는 cycle/slot별 time point 수를 반환합니다."""

    series_index = cycle_idx * len(OES_SLOTS) + (slot_no - 1)
    extra = 1 if series_index < OES_EXTRA_TIME_SERIES else 0
    return OES_BASE_TIME_POINTS + extra


def make_oes_frame(rng: np.random.Generator, *, date: str, cycle_idx: int, type_value: str) -> pd.DataFrame:
    """OES wide raw schema에 맞는 25매 mock frame을 생성합니다."""

    metadata_rows: list[dict[str, object]] = []
    intensity_rows: list[np.ndarray] = []
    wavelength_columns = [_wavelength_column(wavelength) for wavelength in WAVELENGTHS]
    for lot_id, slot_no, wafer_id in _oes_slot_rows():
        time_count = _oes_time_points(cycle_idx=cycle_idx, slot_no=slot_no)
        for rcp_step in RCP_STEPS:
            for time_idx in range(time_count):
                intensity = _oes_intensity_vector(
                    rng,
                    cycle_idx=cycle_idx,
                    type_value=type_value,
                    rcp_step=rcp_step,
                    slot_no=slot_no,
                    time_idx=time_idx,
                    time_count=time_count,
                )
                metadata_rows.append(
                    {
                        "날짜": date,
                        "Time": round(float(time_idx) * 0.125, 3),
                        "rcp_step": rcp_step,
                        "lot_id": lot_id,
                        "slot_no": slot_no,
                        "slot_id": f"SLOT{slot_no:02d}",
                        "wafer_id": wafer_id,
                        "group": f"comp_{lot_id}_{slot_no}",
                        "wafer_end_time": f"{date}T01:{slot_no:02d}:00Z",
                    }
                )
                intensity_rows.append(intensity)
    metadata = pd.DataFrame(metadata_rows)
    spectra = pd.DataFrame(np.vstack(intensity_rows), columns=wavelength_columns)
    frame = pd.concat([metadata, spectra], axis=1)
    return frame.sort_values(["rcp_step", "slot_no", "Time"], kind="stable").reset_index(drop=True)


def save_frame(frame: pd.DataFrame, path: Path, root: Path) -> None:
    """DataFrame을 Parquet 파일로 저장하고 상대 경로를 출력합니다."""

    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False, engine="pyarrow", row_group_size=2500)
    print(f"저장: {path.relative_to(root)} ({len(frame):,}행)")


def main() -> None:
    """PM SPIDER raw mock 파일을 생성합니다."""

    args = parse_args()
    root = args.root.expanduser().resolve()
    rng = np.random.default_rng(args.seed)
    file_count = 0
    row_count = 0

    print("=== PM SPIDER raw mock 데이터 생성 ===")
    print(f"ROOT: {root}")

    for type_value in TYPES:
        for cycle_idx, date in enumerate(PM_DATES):
            for param in TRACE_PARAMS:
                frame = make_trace_frame(rng, date=date, cycle_idx=cycle_idx, type_value=type_value, param=param)
                dest = _partition_dir(
                    root,
                    date=date,
                    type_value=type_value,
                    data_source="trace",
                    trace_param_name=param,
                ) / "data.parquet"
                save_frame(frame, dest, root)
                file_count += 1
                row_count += len(frame)

            oes_frame = make_oes_frame(rng, date=date, cycle_idx=cycle_idx, type_value=type_value)
            oes_dest = _partition_dir(
                root,
                date=date,
                type_value=type_value,
                data_source="oes",
                trace_param_name="spectrum",
            ) / "data.parquet"
            save_frame(oes_frame, oes_dest, root)
            file_count += 1
            row_count += len(oes_frame)

    print("=== 완료 ===")
    print(f"파일 수: {file_count:,}")
    print(f"행 수: {row_count:,}")


if __name__ == "__main__":
    main()
