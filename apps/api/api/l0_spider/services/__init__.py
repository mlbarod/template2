from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from api.l0_spider import selectors

HARD_SPEC_LINE_IDS = ["PFBP", "PFBB", "PFB3", "PFB4", "KFBC", "KFBE", "KFBG", "KFBH", "KFBJ", "KFE3", "KFE5"]
NUMERIC_COLUMNS = ["추천Spec(Lower)", "추천Spec(Upper)", "기존Spec(Lower)", "기존Spec(Upper)"]


class L0SpiderServiceError(Exception):
    """L0 Spider 서비스 오류를 HTTP 상태와 함께 표현합니다."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _safe_value(value: Any) -> Any:
    """JSON 직렬화 가능한 값으로 정리합니다."""

    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return _safe_value(value.item())
    return value


def _split_sensor(value: str) -> tuple[str, str]:
    """sensor 문자열에서 parameter 이름과 cycle을 분리합니다."""

    parts = str(value).rsplit("@", 2)
    if len(parts) == 3:
        return parts[0], f"{parts[1]}@{parts[2]}"
    if len(parts) == 2:
        return parts[0], parts[1]
    return str(value), ""


def _build_step_maps(line_id: str) -> tuple[dict[str, list[str]], dict[str, list[str]], list[str]]:
    """line/model/step 디렉터리에서 hardspec.py와 같은 step option을 만듭니다."""

    line_root = selectors.get_hard_spec_data_root() / line_id
    step_model_dict: dict[str, list[str]] = {}
    ver_step_dict: dict[str, list[str]] = {}

    for model in selectors.list_child_names(line_root):
        for step in selectors.list_child_names(line_root / model):
            step_model_dict.setdefault(step, []).append(model)
            step_key = f"{step[0]}%{step[2:]}" if len(step) >= 3 else step
            ver_step_dict.setdefault(step_key, []).append(step)

    return step_model_dict, ver_step_dict, sorted(ver_step_dict)


def _collect_recipe_context(*, line_id: str, step_seq: str) -> dict[str, Any]:
    """선택된 step_seq에 연결된 PPID/Recipe/FDC model 후보를 수집합니다."""

    line_root = selectors.get_hard_spec_data_root() / line_id
    step_model_dict, ver_step_dict, step_options = _build_step_maps(line_id)
    selected_steps = ver_step_dict.get(step_seq, [])
    eqp_models: set[str] = set()
    recipe_ids: set[str] = set()
    recipe_paths: list[Path] = []

    for selected_step in selected_steps:
        models = step_model_dict.get(selected_step, [])
        eqp_models.update(models)
        for model in models:
            step_root = line_root / model / selected_step
            for ppid in selectors.list_child_names(step_root):
                ppid_root = step_root / ppid
                for recipe_id in selectors.list_child_names(ppid_root):
                    recipe_ids.add(recipe_id)
                    recipe_paths.append(ppid_root / recipe_id)

    warnings: list[str] = []
    try:
        fdc_models = selectors.fetch_fdc_models(step_seq_like=step_seq, eqp_models=sorted(eqp_models))
    except Exception as exc:
        fdc_models = sorted(eqp_models)
        warnings.append(f"FDC model DB 조회 실패로 eqp_model 목록을 사용했습니다: {exc}")

    return {
        "stepOptions": step_options,
        "recipeIds": sorted(recipe_ids),
        "fdcModels": sorted(fdc_models),
        "selectedSteps": selected_steps,
        "eqpModels": sorted(eqp_models),
        "recipePaths": recipe_paths,
        "warnings": warnings,
    }


def _latest_stat_paths(recipe_paths: list[Path], recipe_id: str) -> list[Path]:
    """Recipe 경로별 최신 날짜 데이터를 최대 120개까지 선택합니다."""

    rows: list[dict[str, Any]] = []
    for recipe_path in recipe_paths:
        if recipe_path.name != recipe_id:
            continue
        for date_name in selectors.list_child_names(recipe_path):
            path = recipe_path / date_name
            parts = path.parts[-6:]
            if len(parts) != 6:
                continue
            rows.append(
                {
                    "line": parts[0],
                    "model": parts[1],
                    "step": parts[2],
                    "ppid": parts[3],
                    "rcp": parts[4],
                    "date": parts[5],
                    "path": path,
                }
            )

    if not rows:
        return []

    frame = pd.DataFrame(rows).sort_values("date", ascending=False)
    return list(frame.groupby(["line", "model", "step", "ppid", "rcp"], sort=False)["path"].head(120))


def _load_min_max_data(paths: list[Path]) -> pd.DataFrame:
    """통계 parquet에서 sensor별 추천 Spec min/max를 계산합니다."""

    frames: list[pd.DataFrame] = []
    for path in paths:
        try:
            frames.append(selectors.read_parquet(path, columns=["sensor", "upper_bound", "lower_bound"]))
        except Exception:
            continue

    if not frames:
        return pd.DataFrame(columns=["sensor_name", "cycle", "Lower_Spec", "Upper_Spec"])

    frame = pd.concat(frames, ignore_index=True)
    grouped = frame.groupby("sensor", as_index=False).agg(max=("upper_bound", "max"), min=("lower_bound", "min"))
    grouped["gap"] = (grouped["max"] - grouped["min"]) * 0.05
    grouped["Upper_Spec"] = grouped["max"] + grouped["gap"]
    grouped["Lower_Spec"] = grouped["min"] - grouped["gap"]
    split = grouped["sensor"].map(_split_sensor)
    grouped["sensor_name"] = split.map(lambda item: item[0])
    grouped["cycle"] = split.map(lambda item: item[1])
    return grouped[["sensor_name", "cycle", "Lower_Spec", "Upper_Spec"]]


def _load_priority_sensors(fdc_model: str) -> pd.DataFrame:
    """priority parquet에서 A/B 센서만 조회합니다."""

    frame = selectors.read_parquet(selectors.get_priority_path(), columns=["eqp_id", "priority", "param_name"])
    frame = frame[(frame["eqp_id"] == fdc_model) & (frame["priority"].isin(["A", "B"]))]
    return frame[["param_name", "priority"]].drop_duplicates(subset=["param_name"], keep="first")


def _load_hard_spec(*, fdc_model: str, recipe_id: str, min_max_data: pd.DataFrame) -> pd.DataFrame:
    """unit_model/HARD_LIMIT parquet을 조인해 기존 Hard Spec을 조회합니다."""

    unit_model = selectors.read_parquet(selectors.get_unit_model_path(), columns=["fdc_model", "unit_model_id"])
    unit_model_ids = unit_model.loc[unit_model["fdc_model"] == fdc_model, "unit_model_id"].dropna().unique()
    if len(unit_model_ids) == 0:
        return pd.DataFrame()

    hard_spec = selectors.read_parquet(
        selectors.get_hard_limit_path(),
        columns=["UNIT_MODEL_ID", "PARAMETER_NAME", "RECIPE", "BEGIN_STEP", "END_STEP", "UPDATE_DATE", "UPPER_VALUE", "LOWER_VALUE"],
    )
    hard_spec = hard_spec[
        hard_spec["UNIT_MODEL_ID"].isin(unit_model_ids)
        & hard_spec["PARAMETER_NAME"].isin(min_max_data["sensor_name"].unique())
        & (hard_spec["RECIPE"] == recipe_id)
    ].copy()
    if hard_spec.empty:
        return hard_spec

    min_for_join = min_max_data.rename(columns={"sensor_name": "PARAMETER_NAME"}).copy()
    cycle_split = min_for_join["cycle"].astype(str).str.split("@", n=1, expand=True)
    min_for_join["ch_step_base"] = cycle_split[0].fillna("")
    min_for_join["iter"] = cycle_split[1].fillna("")
    merged = hard_spec.merge(min_for_join, on="PARAMETER_NAME", how="left")
    begin_contains_cycle = merged["BEGIN_STEP"].astype(str).str.match(r"^\d+C\d+$", na=False)
    merged["ch_step"] = np.where(
        begin_contains_cycle,
        merged["ch_step_base"].astype(str) + "C" + merged["iter"].astype(str),
        merged["ch_step_base"].astype(str),
    )
    begin = merged["BEGIN_STEP"].astype(str)
    end = merged["END_STEP"].astype(str)
    ch_step = merged["ch_step"].astype(str)
    merged = merged[((ch_step >= begin) & (ch_step <= end)) | (ch_step == "ALL")]
    merged = merged.sort_values(["PARAMETER_NAME", "cycle", "UPDATE_DATE"]).drop_duplicates(
        subset=["PARAMETER_NAME", "cycle"], keep="last"
    )
    return merged[["PARAMETER_NAME", "cycle", "UPPER_VALUE", "LOWER_VALUE"]]


def get_hard_spec_meta(params: dict[str, Any]) -> dict[str, Any]:
    """Hard Limit 추천 탭의 cascading 선택 옵션을 반환합니다."""

    line_id = params.get("lineId") or HARD_SPEC_LINE_IDS[0]
    step_seq = params.get("stepSeq") or ""
    recipe_id = params.get("recipeId") or ""
    _, _, step_options = _build_step_maps(line_id)
    selected_step_seq = step_seq or (step_options[0] if step_options else "")
    context = (
        _collect_recipe_context(line_id=line_id, step_seq=selected_step_seq)
        if selected_step_seq
        else {"recipeIds": [], "fdcModels": [], "warnings": []}
    )
    selected_recipe_id = recipe_id or (context["recipeIds"][0] if context["recipeIds"] else "")

    return {
        "lineIds": HARD_SPEC_LINE_IDS,
        "lineId": line_id,
        "stepSeq": selected_step_seq,
        "recipeId": selected_recipe_id,
        "stepSeqs": step_options,
        "recipeIds": context["recipeIds"],
        "fdcModels": context["fdcModels"],
        "sourcePaths": {
            "hardSpecRoot": str(selectors.get_hard_spec_data_root() / line_id),
            "priority": str(selectors.get_priority_path()),
            "unitModel": str(selectors.get_unit_model_path()),
            "hardLimit": str(selectors.get_hard_limit_path()),
        },
        "warnings": context["warnings"],
    }


def get_hard_spec_recommendations(params: dict[str, Any]) -> dict[str, Any]:
    """hardspec.py의 Hard Limit 추천 계산 결과를 반환합니다."""

    line_id = params["lineId"]
    step_seq = params["stepSeq"]
    recipe_id = params["recipeId"]
    fdc_model = params["fdcModel"]
    context = _collect_recipe_context(line_id=line_id, step_seq=step_seq)
    stat_paths = _latest_stat_paths(context["recipePaths"], recipe_id)
    min_max_data = _load_min_max_data(stat_paths)
    if min_max_data.empty:
        return {"rows": [], "chartRows": [], "sourcePaths": [str(path) for path in stat_paths], "warnings": [*context["warnings"], "선택 조건에 맞는 통계 parquet 데이터가 없습니다."]}

    priority_sensors = _load_priority_sensors(fdc_model).rename(columns={"param_name": "sensor_name"})
    min_max_data = min_max_data.merge(priority_sensors, on="sensor_name", how="left")
    min_max_data = min_max_data[min_max_data["priority"].isin(["A", "B"])].sort_values(["priority", "sensor_name"])
    if min_max_data.empty:
        return {"rows": [], "chartRows": [], "sourcePaths": [str(path) for path in stat_paths], "warnings": [*context["warnings"], "선택 FDC model의 A/B priority 센서가 없습니다."]}

    hard_spec = _load_hard_spec(fdc_model=fdc_model, recipe_id=recipe_id, min_max_data=min_max_data)
    if hard_spec.empty:
        return {"rows": [], "chartRows": [], "sourcePaths": [str(path) for path in stat_paths], "warnings": [*context["warnings"], "선택 조건에 맞는 HARD_LIMIT 데이터가 없습니다."]}

    result = min_max_data.merge(
        hard_spec.rename(columns={"PARAMETER_NAME": "sensor_name"}),
        on=["sensor_name", "cycle"],
        how="inner",
    ).rename(
        columns={
            "cycle": "ch_step",
            "Lower_Spec": "추천Spec(Lower)",
            "Upper_Spec": "추천Spec(Upper)",
            "LOWER_VALUE": "기존Spec(Lower)",
            "UPPER_VALUE": "기존Spec(Upper)",
        }
    )
    for column in NUMERIC_COLUMNS:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result["HARD_gap"] = result["기존Spec(Upper)"] - result["기존Spec(Lower)"]
    result["Reco_gap"] = result["추천Spec(Upper)"] - result["추천Spec(Lower)"]
    result["ratio"] = (result["HARD_gap"] / result["Reco_gap"]).round(1).replace([np.inf, -np.inf], 0)
    result["Spec격차"] = result["ratio"].map(lambda value: "-배" if value == 0 else f"{value:.1f}배")
    result = result.sort_values("ratio", ascending=False)
    result = result[result["ch_step"].astype(str).str.contains(r"^\d+@(?:001|01)$", regex=True, na=False)]

    rows = []
    columns = ["priority", "sensor_name", "ch_step", *NUMERIC_COLUMNS, "Spec격차"]
    for index, row in result[columns].iterrows():
        item = {column: _safe_value(row[column]) for column in columns}
        item["id"] = f"{item['sensor_name']}::{item['ch_step']}::{index}"
        rows.append(item)

    return {
        "rows": rows,
        "chartRows": [],
        "sourcePaths": [str(path) for path in stat_paths[:120]],
        "warnings": context["warnings"],
    }
