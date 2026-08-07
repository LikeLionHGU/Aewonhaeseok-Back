#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""apply_review.py가 남긴 review_log.csv를 정규화 원본(source/)에 되돌린다.

왜 필요한가
-----------
사전은 두 형태로 존재한다.

    source/term_synonyms.csv   원본. 동의어 1건 = 1행, 출처·수집일이 각각 붙는다.
    ontology/*.csv             엔진이 읽는 평면 투영. export_ontology.py가 만든다.

pipeline/apply_review.py는 사람이 판정한 동의어를 **평면 쪽에** 써넣는다.
그 상태에서 export_ontology.py를 다시 돌리면 평면이 원본으로부터 새로 만들어지므로
사람이 승인한 동의어가 조용히 사라진다.

이 스크립트가 그 구멍을 막는다. apply_review.py가 함께 남기는 review_log.csv에는
code / synonym / source(출처파일) / collected_at / reviewer 가 있어서,
원본 term_synonyms.csv가 요구하는 출처·수집일을 그대로 채울 수 있다.

운영 순서
---------
    python run.py ./data/samples/                  # 매핑 → review_queue.csv
    (사람이 review_queue.csv의 '사람판정' 칸을 채운다)
    python pipeline/apply_review.py output/review_queue.csv
    python ontology/import_review_log.py           # ← 원본에 반영 (이 스크립트)
    python ontology/export_ontology.py             # 평면 재생성

실행
----
    python3 ontology/import_review_log.py [--dry-run]
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "source"
SYNONYM_FILE = SOURCE / "term_synonyms.csv"
SOURCES_FILE = SOURCE / "term_sources.csv"
LOG_FILE = HERE / "review_log.csv"

# 사람 검수를 거쳐 들어온 동의어의 출처. term_sources.csv에 없으면 만들어 넣는다.
REVIEW_SOURCE_ID = "HUMAN_REVIEW"
REVIEW_SOURCE_ROW = {
    "source_id": REVIEW_SOURCE_ID,
    "source_name": "매핑 파이프라인 리뷰 대기열 승인분",
    "organization": "팀 자체 검수",
    "source_type": "manual",
    "base_url": "",
    "access_note": "run.py가 만든 review_queue.csv를 사람이 판정하고 apply_review.py로 반영한 것. "
                   "원본 데이터 파일명은 각 동의어의 evidence_snippet에 남는다",
    "encoding": "UTF-8",
    "reliability": "observed",
}

sys.path.insert(0, str(HERE.parent))
try:
    from pipeline.mapper import normalize as _normalize
except ImportError:
    _normalize = None


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in columns})


def _norm(text: str) -> str:
    if _normalize is None:
        return "".join(ch for ch in text.lower() if ch.isalnum())
    return _normalize(text).body


def main() -> int:
    ap = argparse.ArgumentParser(description="리뷰 반영 이력을 정규화 원본에 되돌린다")
    ap.add_argument("--log", default=str(LOG_FILE), help="review_log.csv 경로")
    ap.add_argument("--dry-run", action="store_true", help="파일을 쓰지 않고 무엇이 들어갈지만 출력")
    args = ap.parse_args()

    log_path = Path(args.log)
    if not log_path.exists():
        print(f"반영할 이력이 없습니다: {log_path}")
        return 0

    log = read_csv(log_path)
    if not log:
        print("review_log.csv가 비어 있습니다.")
        return 0

    syn_rows = read_csv(SYNONYM_FILE)
    syn_cols = list(syn_rows[0].keys())

    # 이미 원본에 있는 (코드, 정규화표기)는 다시 넣지 않는다
    existing = {(r["measurement_code"] or r["metadata_code"], _norm(r["surface"]))
                for r in syn_rows}

    added = []
    for r in log:
        code = r["code"].strip()
        surface = r["synonym"].strip()
        if not code or not surface:
            continue
        key = (code, _norm(surface))
        if key in existing:
            continue
        existing.add(key)
        added.append({
            "term_kind": "measurement" if code.startswith("WQ-") else "metadata",
            "measurement_code": code if code.startswith("WQ-") else "",
            "metadata_code": code if code.startswith("MD-") else "",
            "surface": surface,
            "source_id": REVIEW_SOURCE_ID,
            # apply_review.py가 남긴 시각(ISO)에서 날짜만 취한다
            "collected_on": (r.get("collected_at") or "")[:10],
            "evidence_url": "",
            "evidence_snippet": f"출처파일: {r.get('source', '')}",
            "synonym_type": "column_name",
            "review_status": "verified",
            "note": f"리뷰 대기열 승인 (판정자: {r.get('reviewer') or '미기재'})",
        })

    if not added:
        print("새로 반영할 동의어가 없습니다 (모두 이미 원본에 있음).")
        return 0

    print(f"원본에 추가할 동의어 {len(added)}건:")
    for a in added:
        code = a["measurement_code"] or a["metadata_code"]
        print(f"  {code:8s} += '{a['surface']}'   ({a['note']})")

    if args.dry_run:
        print("\n--dry-run 이므로 파일을 쓰지 않았습니다.")
        return 0

    # 출처 레지스트리에 HUMAN_REVIEW가 없으면 추가
    src_rows = read_csv(SOURCES_FILE)
    if not any(r["source_id"] == REVIEW_SOURCE_ID for r in src_rows):
        src_rows.append(REVIEW_SOURCE_ROW)
        write_csv(SOURCES_FILE, list(src_rows[0].keys()), src_rows)
        print(f"\nterm_sources.csv에 '{REVIEW_SOURCE_ID}' 출처를 추가했습니다.")

    write_csv(SYNONYM_FILE, syn_cols, syn_rows + added)
    print(f"\n{SYNONYM_FILE.name}에 {len(added)}건 반영했습니다.")
    print("이제 export_ontology.py를 다시 돌려 평면 사전을 재생성하세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
