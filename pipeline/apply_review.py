"""review_queue.csv의 사람 판정 결과를 표준 사전 synonyms에 반영한다.

    python pipeline/apply_review.py output/review_queue.csv [--ontology ontology]

사람판정 칸 규칙:
  - 표준코드 직접 기입 (예: WQ-TN)      → 그 코드의 synonyms에 원본명 추가
  - '승인' / 'accept' / 'y' / 'ok'     → 후보 표준코드 채택
  - '기각' / 'reject' / 'x' / 빈칸     → 반영하지 않음

반영 시 ontology/review_log.csv에 source(출처파일), collected_at, 판정자를 함께 기록한다.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline import config
from pipeline.mapper import normalize

ACCEPT_VALUES = {"승인", "accept", "y", "yes", "ok"}
REJECT_VALUES = {"기각", "reject", "x", "no", "제외", "skip"}

LOG_COLUMNS = ["dict_file", "code", "synonym", "source", "collected_at", "reviewer"]


def _load_dict(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("")


def _existing_norms(row: pd.Series) -> set[str]:
    variants = [row.get("name_ko", ""), row.get("name_en", ""), row.get("abbr", "")]
    variants += str(row.get("synonyms", "") or "").split("|")
    return {normalize(v).body for v in variants if str(v).strip()}


def apply_review(queue_path: Path, ontology_dir: Path) -> pd.DataFrame:
    """판정 결과를 사전에 반영하고, 반영 내역(log) DataFrame을 반환한다."""
    queue = pd.read_csv(queue_path, dtype=str, encoding="utf-8-sig").fillna("")

    dict_paths = {
        "measurement": ontology_dir / config.MEASUREMENT_DICT_FILENAME,
        "metadata": ontology_dir / config.METADATA_DICT_FILENAME,
    }
    dicts = {k: _load_dict(p) for k, p in dict_paths.items()}
    changed = {k: False for k in dicts}
    log_rows = []

    for _, row in queue.iterrows():
        verdict = str(row.get("사람판정", "")).strip()
        if not verdict or verdict.lower() in REJECT_VALUES:
            continue

        if verdict.lower() in ACCEPT_VALUES:
            code = str(row.get("후보 표준코드", "")).strip()
            if not code:
                print(f"[경고] '{row['원본명']}': 판정이 '{verdict}'인데 후보 표준코드가 없어 건너뜀")
                continue
        else:
            code = verdict  # 표준코드 직접 기입

        target_key = None
        for key, df in dicts.items():
            if (df["code"] == code).any():
                target_key = key
                break
        if target_key is None:
            print(f"[경고] '{row['원본명']}': 표준코드 '{code}' 를 어느 사전에서도 찾지 못해 건너뜀")
            continue

        df = dicts[target_key]
        idx = df.index[df["code"] == code][0]
        raw_name = str(row["원본명"]).strip()

        if normalize(raw_name).body in _existing_norms(df.loc[idx]):
            print(f"[안내] '{raw_name}' 은 이미 {code} 표기에 포함되어 있어 건너뜀")
            continue

        syn = str(df.at[idx, "synonyms"]).strip()
        df.at[idx, "synonyms"] = f"{syn}|{raw_name}" if syn else raw_name
        changed[target_key] = True

        log_rows.append({
            "dict_file": dict_paths[target_key].name,
            "code": code,
            "synonym": raw_name,
            "source": str(row.get("출처파일", "")).strip(),
            "collected_at": datetime.now().isoformat(timespec="seconds"),
            "reviewer": str(row.get("판정자", "")).strip(),
        })
        print(f"[반영] {code} synonyms += '{raw_name}' (출처: {row.get('출처파일', '')})")

    for key, df in dicts.items():
        if changed[key]:
            df.to_csv(dict_paths[key], index=False, encoding="utf-8-sig")

    log = pd.DataFrame(log_rows, columns=LOG_COLUMNS)
    if not log.empty:
        log_path = ontology_dir / "review_log.csv"
        if log_path.exists():
            old = pd.read_csv(log_path, dtype=str)
            log = pd.concat([old, log], ignore_index=True)
        log.to_csv(log_path, index=False, encoding="utf-8-sig")
        print(f"반영 {len(log_rows)}건, 기록: {log_path}")
    else:
        print("반영할 판정이 없습니다.")
    return log


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="리뷰 판정 결과를 표준 사전에 반영")
    parser.add_argument("queue", help="판정 컬럼을 채운 review_queue.csv 경로")
    parser.add_argument("--ontology", default=config.ONTOLOGY_DIR, help="표준 사전 디렉토리")
    args = parser.parse_args(argv)
    apply_review(Path(args.queue), Path(args.ontology))


if __name__ == "__main__":
    main()
