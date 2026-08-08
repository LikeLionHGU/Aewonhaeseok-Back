#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""정규화 사전(source/) → 매핑 엔진이 읽는 평면 사전(ontology/*.csv).

왜 변환이 필요한가
------------------
사전의 원본은 source/ 아래 정규화된 4개 테이블이다. 동의어 한 건이 한 행이고
출처(source_id)와 수집일(collected_on)이 각각 붙어 있다. 근거를 남기려면 이 형태여야 한다.

반면 pipeline/mapper.py 는 한 항목이 한 행이고 동의어가 파이프로 이어 붙은 평면 형태를
읽는다(code / name_ko / name_en / abbr / synonyms). 그래서 원본을 평면으로 투영해 준다.

    source/measurement_terms.csv  ─┐
    source/metadata_terms.csv      ├─→  ontology/measurement_terms.csv
    source/term_synonyms.csv      ─┘    ontology/metadata_terms.csv
    source/term_sources.csv

주의
----
* ontology/*.csv 는 **생성물이다.** 손으로 고치지 마라. 이 스크립트가 덮어쓴다.
* pipeline/apply_review.py 는 ontology/*.csv 의 synonyms 에 직접 써넣는다.
  그 추가분을 원본에 되돌리지 않고 이 스크립트를 다시 돌리면 사라진다.
  반드시 import_review_log.py 를 먼저 돌려 원본에 반영한 뒤 재생성할 것.

실행
----
    python3 ontology/export_ontology.py                 # 전체 동의어 포함
    python3 ontology/export_ontology.py --exclude-inferred   # 미검증(AI 추정) 제외
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "source"

# 엔진과 똑같은 정규화 규칙으로 중복 동의어를 판정해야 한다.
sys.path.insert(0, str(HERE.parent))
try:
    from pipeline.mapper import normalize as _normalize
except ImportError:  # 엔진 없이 CSV만 뽑을 때
    _normalize = None

# 매핑 엔진이 실제로 읽는 컬럼 (pipeline/mapper.py의 _VARIANT_FIELDS + synonyms).
# 이 다섯 개가 없으면 매칭이 조용히 망가진다.
ENGINE_FIELDS = ["code", "name_ko", "name_en", "abbr", "synonyms"]

MEASUREMENT_COLUMNS = ENGINE_FIELDS + [
    "unit", "category", "legal_basis", "verified", "note",
    # 아래는 엔진이 읽지 않는 참고용 컬럼. 근거를 파일 안에 남겨 두기 위해 붙인다.
    "legal_status", "is_toxic_substance", "toxic_substance_basis",
    "legal_article", "legal_effective_from", "synonym_count", "source_count",
]

METADATA_COLUMNS = ENGINE_FIELDS + [
    "unit", "category", "reference", "verified", "note",
    "value_type", "std_domain", "canonical_format", "normalization_note",
    "synonym_count", "source_count",
]


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def collect_synonyms(rows: list[dict], sources: dict[str, str],
                     exclude_inferred: bool) -> tuple[dict, dict, dict]:
    """표준코드별 (동의어 표기 목록, 동의어 수, 출처 수)를 모은다.

    같은 표기가 여러 기관에서 관측돼도 평면 형태에서는 한 번만 적는다.
    어느 기관이 언제 그렇게 쓰는지는 source/term_synonyms.csv 를 봐야 한다.
    """
    surfaces: dict[str, list[str]] = defaultdict(list)
    seen: dict[str, set[str]] = defaultdict(set)
    n_syn: dict[str, int] = defaultdict(int)
    src_set: dict[str, set[str]] = defaultdict(set)

    for r in rows:
        if r["review_status"] == "rejected":
            continue
        if exclude_inferred and sources.get(r["source_id"]) == "inferred":
            continue
        code = r["measurement_code"] or r["metadata_code"]
        surface = r["surface"].strip()
        if not surface:
            continue
        n_syn[code] += 1
        src_set[code].add(r["source_id"])
        if surface not in seen[code]:
            seen[code].add(surface)
            surfaces[code].append(surface)
    return surfaces, n_syn, src_set


def _keys(variant: str) -> set[str]:
    """엔진이 이 표기로 만들 색인 키(본체 + 괄호부 약어 토큰)."""
    if _normalize is None:
        return {variant.strip().lower()}
    n = _normalize(variant)
    keys = set(n.paren_tokens)
    if n.body:
        keys.add(n.body)
    return keys


def build_rows(terms: list[dict], surfaces, n_syn, src_set, kind: str) -> list[dict]:
    out = []
    n_redundant = 0
    for t in terms:
        # rejected 항목은 엔진 사전에 넣지 않는다. 근거가 없어 매칭되면 안 된다.
        if t["review_status"] == "rejected":
            continue
        code = t["code"]
        name_ko = t["std_name"]
        name_en = t.get("name_en", "")
        abbr = t.get("abbr", "")

        # 본체(괄호를 뗀 부분)가 이미 색인된 동의어는 뺀다.
        #
        # 본체만으로 이미 매칭되므로 사전에 둘 이유가 없는데, 괄호부는 약어 후보로
        # 따로 색인되기 때문에 오히려 해롭다. 예를 들어 '총인(total phosphorus)'은
        # 본체가 '총인'이라 표준명과 같지만, 괄호부에서 'total'이 약어로 잡혀
        # '총질소(total nitrogen)'와 충돌한다. 'total'은 약어가 아니라 일반 단어다.
        #
        # 진짜 약어는 abbr 컬럼에 있어야지 괄호부에서 우연히 주워지면 안 된다.
        indexed: set[str] = set()
        for v in (name_ko, name_en, abbr):
            if v and v != "-":
                indexed |= _keys(v)

        syn = []
        for s in surfaces.get(code, []):
            body = _normalize(s).body if _normalize else s.strip().lower()
            if body and body in indexed:
                n_redundant += 1
                continue
            indexed |= _keys(s)
            syn.append(s)

        row = {
            "code": code,
            "name_ko": name_ko,
            "name_en": name_en,
            "abbr": "" if abbr == "-" else abbr,
            "synonyms": "|".join(syn),
            "unit": t.get("unit", ""),
            "verified": "Y" if t["review_status"] == "verified" else "N",
            "note": t.get("note", ""),
            "synonym_count": n_syn.get(code, 0),
            "source_count": len(src_set.get(code, ())),
        }
        if kind == "measurement":
            row.update({
                "category": t.get("category", ""),
                "legal_basis": t.get("legal_basis", ""),
                "legal_status": t.get("legal_status", ""),
                "is_toxic_substance": t.get("is_toxic_substance", ""),
                "toxic_substance_basis": t.get("toxic_substance_basis", ""),
                "legal_article": t.get("legal_article", ""),
                "legal_effective_from": t.get("legal_effective_from", ""),
            })
        else:
            row.update({
                "category": t.get("facet", ""),
                "reference": t.get("standard_basis", ""),
                "value_type": t.get("value_type", ""),
                "std_domain": t.get("std_domain", ""),
                "canonical_format": t.get("canonical_format", ""),
                "normalization_note": t.get("normalization_note", ""),
            })
        out.append(row)
    if n_redundant:
        print(f"  (정규화하면 기존 표기와 같아지는 동의어 {n_redundant}건은 색인에서 생략 — "
              f"근거는 source/term_synonyms.csv에 그대로 남아 있다)")
    return out


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in columns})


def main() -> int:
    ap = argparse.ArgumentParser(description="정규화 사전을 매핑 엔진 형식으로 내보낸다")
    ap.add_argument("--exclude-inferred", action="store_true",
                    help="출처 신뢰도가 inferred(AI 추정, 미검증)인 동의어를 제외한다")
    args = ap.parse_args()

    measurement = read_csv(SOURCE / "measurement_terms.csv")
    metadata = read_csv(SOURCE / "metadata_terms.csv")
    synonyms = read_csv(SOURCE / "term_synonyms.csv")
    sources = {r["source_id"]: r["reliability"]
               for r in read_csv(SOURCE / "term_sources.csv")}

    surfaces, n_syn, src_set = collect_synonyms(synonyms, sources, args.exclude_inferred)

    m_rows = build_rows(measurement, surfaces, n_syn, src_set, "measurement")
    d_rows = build_rows(metadata, surfaces, n_syn, src_set, "metadata")

    write_csv(HERE / "measurement_terms.csv", MEASUREMENT_COLUMNS, m_rows)
    write_csv(HERE / "metadata_terms.csv", METADATA_COLUMNS, d_rows)

    n_dropped = len(measurement) + len(metadata) - len(m_rows) - len(d_rows)
    print(f"measurement_terms.csv  {len(m_rows):3d}행  "
          f"동의어 {sum(len(r['synonyms'].split('|')) if r['synonyms'] else 0 for r in m_rows):3d}개")
    print(f"metadata_terms.csv     {len(d_rows):3d}행  "
          f"동의어 {sum(len(r['synonyms'].split('|')) if r['synonyms'] else 0 for r in d_rows):3d}개")
    if n_dropped:
        print(f"제외(rejected)          {n_dropped}행")
    if args.exclude_inferred:
        print("미검증(AI 추정) 동의어는 제외했다")

    # 엔진이 실제로 로딩되는지 여기서 바로 확인한다. 사전 표기 충돌은
    # load_lexicon()이 DictionaryConflictError로 즉시 실패시키므로 배포 전에 잡아야 한다.

    try:
        from pipeline.mapper import DictionaryConflictError, load_lexicon
    except ImportError as e:
        print(f"\n[건너뜀] 엔진 로딩 검증 불가: {e}")
        return 0

    try:
        lex = load_lexicon(HERE / "measurement_terms.csv", HERE / "metadata_terms.csv")
    except DictionaryConflictError as e:
        print(f"\n[실패] 사전 표기 충돌\n{e}")
        return 1
    print(f"\n엔진 로딩 확인: 색인 {len(lex.exact_index)}개 표기")

    # 사전 버전 스탬프. 손으로 쓰지 않고 여기서 함께 만든다 —
    # 사람이 올리는 번호는 반드시 잊어버린다.
    from pipeline.version import VERSION_FILENAME, build_version, write_version

    n_verified = sum(1 for r in m_rows + d_rows if str(r.get("verified", "")).strip() == "Y")
    v = build_version(
        HERE / "measurement_terms.csv",
        HERE / "metadata_terms.csv",
        measurement_terms=len(m_rows),
        metadata_terms=len(d_rows),
        synonyms=sum(len(r["synonyms"].split("|")) if r["synonyms"] else 0
                     for r in m_rows + d_rows),
        verified_terms=n_verified,
        excluded_inferred=args.exclude_inferred,
        note="미검증(AI 추정) 동의어를 제외한 사전" if args.exclude_inferred else "",
    )
    write_version(HERE / VERSION_FILENAME, v)
    print(f"사전 버전: {v.version}  (내용 해시 {v.content_hash})")
    print(f"  → {HERE / VERSION_FILENAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
