"""
[대시보드 서버에서 실행]

daily_anomaly 안의 mock parquet 파일들을 스캔해서 SQLite 인덱스를 만듭니다.
알고리즘 서버 코드(config.py, persistence.py)에 의존하지 않는 완전 독립
스크립트입니다 — 대시보드 서버 환경(pandas + pyarrow)만으로 동작합니다.

목적 : dashboard_index_reader.py 를 실제로 붙이기 전에, 인덱스가 만들어지고
      쿼리가 기대한 대로 나오는지 mock 데이터로 미리 확인하는 것.

사용법:
  python build_mock_index.py --root /data/l3_spider/daily_anomaly

  # 인덱스 새로 만들지 않고 기존 것만 검증
  python build_mock_index.py --root /data/l3_spider/daily_anomaly --verify-only

옵션:
  --root   daily_anomaly 최상위 경로 (필수)
  --db     인덱스 파일 경로 (기본: {root}/_meta/index.sqlite3, 실제 이상과 동일)
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

try:
    import pandas as pd
except ImportError:
    print("✗ pandas 가 없습니다. 대시보드 서버 환경(Django 컨테이너 등)에서 실행해주세요.")
    sys.exit(1)


REQUIRED_COLUMNS = {"eqp_id", "chamber_id", "bin_name", "display_status"}


# ───────────────────────────────────────────────
# 스캔 / 파싱
# ───────────────────────────────────────────────

def iter_saved_files(root: Path) -> Iterator[Path]:
    """저장 트리: {root}/{date}/{line_id}/{process_id}/{eds_step}/*"""
    for date_dir in sorted(root.iterdir()):
        if not date_dir.is_dir() or date_dir.name.startswith("_"):
            continue  # _meta 등 비-날짜 항목 제외
        yield from (f for f in date_dir.rglob("*") if f.is_file())


def parse_path_meta(f: Path, root: Path) -> Optional[dict]:
    """경로에서 date/line_id/process_id/eds_step, 파일명에서 step_seq#ppid 추출."""
    try:
        rel = f.relative_to(root)
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) < 5:
        return None
    save_date, line_id, process_id, eds_step = parts[0], parts[1], parts[2], parts[3]
    name_parts = f.name.split("#")
    if len(name_parts) < 2:
        return None
    return {
        "save_date": save_date, "line_id": line_id, "process_id": process_id,
        "eds_step": eds_step, "step_seq": name_parts[0], "ppid": name_parts[1],
    }


# ───────────────────────────────────────────────
# SQLite 인덱스 (persistence.py 와 동일 스키마)
# ───────────────────────────────────────────────

def ensure_index_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS file_index (
            filepath      TEXT PRIMARY KEY,
            date          TEXT NOT NULL,
            line_id       TEXT NOT NULL,
            process_id    TEXT NOT NULL,
            eds_step      TEXT NOT NULL,
            step_seq      TEXT NOT NULL,
            ppid          TEXT NOT NULL,
            eqp_ids       TEXT NOT NULL,
            chamber_ids   TEXT NOT NULL,
            bin_names     TEXT NOT NULL,
            row_cnt       INTEGER,
            has_high_risk INTEGER DEFAULT 0,
            high_risk_cnt INTEGER,
            warning_cnt   INTEGER,
            normal_cnt    INTEGER,
            high_risk_eqcs TEXT,
            total_bin_cnt INTEGER,
            saved_at      TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_date_line ON file_index(date, line_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_date_hr   ON file_index(date, has_high_risk)")
    # 날짜별 알고리즘 런 완료 상태. 대시보드는 status='completed' 날짜만 노출한다.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS run_status (
            date         TEXT PRIMARY KEY,
            status       TEXT NOT NULL,   -- 'running' | 'completed'
            completed_at TEXT
        )
    """)


def upsert_file_group(conn: sqlite3.Connection, files: list[Path], meta: dict, df: pd.DataFrame, root: Path) -> None:
    eqp_ids     = sorted(df["eqp_id"].astype(str).unique().tolist())
    chamber_ids = sorted(df["chamber_id"].astype(str).unique().tolist())
    bin_names   = sorted(df["bin_name"].astype(str).unique().tolist())
    # 상태 정규화(대시보드와 동일): 'Single Spike' → 'Warning'
    status = df["display_status"].astype(str).replace({"Single Spike": "Warning"})
    has_hr      = bool((status == "High Risk Chamber").any())
    # 상태별 카운트: 이게 있어야 대시보드가 parquet 재읽기 없이 인덱스만으로 요약을 집계함(수백배 빠름).
    high_risk_cnt = int((status == "High Risk Chamber").sum())
    warning_cnt   = int((status == "Warning").sum())
    normal_cnt    = int((status == "Normal (Ref)").sum())
    # High Risk가 난 distinct EQPCH(eqc) 목록 — 이상 EQPCH 지표용
    if "eqc" in df.columns:
        high_risk_eqcs = sorted(
            e for e in df.loc[status == "High Risk Chamber", "eqc"].dropna().astype(str).unique().tolist() if e
        )
    else:
        high_risk_eqcs = []
    # 분석 그룹용: 이상 여부와 무관하게 이 파일에서 처리된 전체 고유 bin 수.
    # (mock parquet은 정상 포함 전체 행을 담고 있어 nunique = 전체 bin 수)
    total_bin_cnt = int(df["bin_name"].astype(str).nunique())
    saved_at    = datetime.now().isoformat(timespec="seconds")

    for f in files:
        # root 기준 상대 경로를 저장 — selectors.py가 data_root를 prefix로 붙여 절대 경로로 복원함
        rel_path = f.relative_to(root).as_posix()
        conn.execute("""
            INSERT INTO file_index
                (filepath, date, line_id, process_id, eds_step, step_seq, ppid,
                 eqp_ids, chamber_ids, bin_names, row_cnt, has_high_risk,
                 high_risk_cnt, warning_cnt, normal_cnt, high_risk_eqcs, total_bin_cnt, saved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(filepath) DO UPDATE SET
                eqp_ids        = excluded.eqp_ids,
                chamber_ids    = excluded.chamber_ids,
                bin_names      = excluded.bin_names,
                row_cnt        = excluded.row_cnt,
                has_high_risk  = excluded.has_high_risk,
                high_risk_cnt  = excluded.high_risk_cnt,
                warning_cnt    = excluded.warning_cnt,
                normal_cnt     = excluded.normal_cnt,
                high_risk_eqcs = excluded.high_risk_eqcs,
                total_bin_cnt  = excluded.total_bin_cnt,
                saved_at       = excluded.saved_at
        """, (
            rel_path, meta["save_date"], meta["line_id"], meta["process_id"],
            meta["eds_step"], meta["step_seq"], meta["ppid"],
            json.dumps(eqp_ids), json.dumps(chamber_ids), json.dumps(bin_names),
            len(df), int(has_hr),
            high_risk_cnt, warning_cnt, normal_cnt, json.dumps(high_risk_eqcs), total_bin_cnt, saved_at,
        ))


def build_index(root: Path, db_path: Path) -> None:
    files = list(iter_saved_files(root))
    print(f"대상 파일 수: {len(files)}")
    if not files:
        print("⚠️  mock 데이터를 찾지 못했습니다. --root 경로를 확인하세요.")
        return

    groups: dict[tuple, list[Path]] = defaultdict(list)
    metas: dict[tuple, dict] = {}
    for f in files:
        meta = parse_path_meta(f, root)
        if meta is None:
            print(f"  [skip] 경로/파일명 파싱 실패: {f}")
            continue
        key = (meta["save_date"], meta["line_id"], meta["process_id"],
               meta["eds_step"], meta["step_seq"], meta["ppid"])
        groups[key].append(f)
        metas[key] = meta

    print(f"파티션 그룹 수: {len(groups)}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA journal_mode = DELETE")
    ensure_index_schema(conn)

    ok, fail = 0, 0
    seen_dates: set[str] = set()
    with conn:
        conn.execute("DELETE FROM file_index")
        for key, group_files in groups.items():
            meta = metas[key]
            try:
                df = pd.read_parquet(group_files, engine="pyarrow")
            except Exception as e:
                print(f"  [skip] 읽기 실패 {group_files}: {e}")
                fail += 1
                continue
            if not REQUIRED_COLUMNS.issubset(df.columns):
                print(f"  [skip] 컬럼 부족 {group_files}: {REQUIRED_COLUMNS - set(df.columns)}")
                fail += 1
                continue
            upsert_file_group(conn, group_files, meta, df, root)
            seen_dates.add(meta["save_date"])
            ok += 1

        # mock 데이터의 모든 날짜는 완료된 것으로 표시(실제 알고리즘 서버는 런 종료 시 기록).
        conn.execute("DELETE FROM run_status")
        completed_at = datetime.now().isoformat(timespec="seconds")
        for d in sorted(seen_dates):
            conn.execute(
                "INSERT INTO run_status (date, status, completed_at) VALUES (?, 'completed', ?)",
                (d, completed_at),
            )

    conn.close()
    print(f"\n✓ 인덱스 생성 완료: 성공 {ok} / 실패 {fail} (DB: {db_path})")


# ───────────────────────────────────────────────
# 검증 — 대시보드에서 실제 쿼리 방식과 동일하게 확인
# ───────────────────────────────────────────────

def verify_index(db_path: Path, root: Path) -> None:
    if not db_path.exists():
        print(f"✗ 인덱스 파일 없음: {db_path}")
        return

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)

    total = conn.execute("SELECT COUNT(*) FROM file_index").fetchone()[0]
    print(f"\n{'='*60}")
    print(f"검증: 총 {total}건 인덱싱됨")
    print(f"{'='*60}")

    if total == 0:
        conn.close()
        return

    print("\n[날짜별 건수]")
    for row in conn.execute("""
        SELECT date, COUNT(*) FROM file_index GROUP BY date ORDER BY date DESC LIMIT 10
    """):
        print(f"  {row[0]}: {row[1]}건")

    print("\n[샘플 5건 — filepath 는 상대경로로 저장됨]")
    for row in conn.execute("""
        SELECT date, line_id, process_id, filepath, eqp_ids, has_high_risk
        FROM file_index LIMIT 5
    """):
        resolved = root / row[3]
        exists = resolved.exists()
        mark = "✓" if exists else "✗ 파일 없음"
        print(f"  date={row[0]} line={row[1]} process={row[2]}")
        print(f"    filepath(저장값, 상대경로)={row[3]}")
        print(f"    root 와 결합한 실제 경로={resolved}  {mark}")

    # 실제 dashboard_index_reader.py 의 query_indexed_files() 와 동일한 쿼리로
    # eqp_id 필터가 실제로 동작하는지, 그리고 나온 상대경로가 root 와 결합해서
    # 실제 파일을 가리키는지까지 확인 — 이게 통과하면 대시보드 쪽 read_parquet() 도
    # 그대로 성공한다는 뜻입니다.
    sample = conn.execute("SELECT date, eqp_ids FROM file_index LIMIT 1").fetchone()
    if sample:
        sample_date = sample[0]
        sample_eqp = json.loads(sample[1])[0]
        print(f"\n[eqp_id 필터 쿼리 테스트: date={sample_date}, eqp_id={sample_eqp}]")
        result = conn.execute("""
            SELECT filepath FROM file_index
            WHERE date = ? AND EXISTS (
                SELECT 1 FROM json_each(eqp_ids) WHERE value = ?
            )
        """, (sample_date, sample_eqp)).fetchall()
        print(f"  매칭 결과: {len(result)}건")
        if result:
            all_exist = all((root / r[0]).exists() for r in result)
            if all_exist:
                print(f"  ✓ json_each 필터 쿼리 정상 동작 + 모든 파일 실제 존재 확인")
                print(f"     (dashboard_index_reader.py 로 대시보드에서 받아온 경로에")
                print(f"      대시보드 쪽 root 만 붙이면 그대로 read_parquet() 가능)")
            else:
                print(f"  ⚠️  쿼리는 매칭됐지만 일부 파일이 실제로 없습니다 — root 경로 확인 필요")
        else:
            print(f"  ✗ 매칭 안 됨 → 스키마나 데이터 확인 필요")

    conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="mock 데이터로 SQLite 인덱스 생성/검증")
    ap.add_argument("--root", required=True, help="daily_anomaly 최상위 경로")
    ap.add_argument("--db", default=None, help="인덱스 파일 경로 (기본: {root}/_meta/index.sqlite3)")
    ap.add_argument("--verify-only", action="store_true", help="생성 없이 기존 인덱스만 검증")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        print(f"✗ 경로 없음: {root}")
        sys.exit(1)

    db_path = Path(args.db) if args.db else root / "_meta" / "index.sqlite3"

    if not args.verify_only:
        build_index(root, db_path)

    verify_index(db_path, root)


if __name__ == "__main__":
    main()
