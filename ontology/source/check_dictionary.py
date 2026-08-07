#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
사전 자체 점검 + 매칭 시연.

PostgreSQL 없이도 돌아가도록 wq_normalize / wq_match_column과 같은 로직을
파이썬으로 재현한다. DB에 올린 뒤에는 SQL 쪽이 원본이고 이 파일은 회귀 테스트용이다.

실행:  python3 ontology/source/check_dictionary.py

파일명에 test_ 접두를 쓰지 않는 이유: pytest가 테스트 파일로 수집해 버린다.
이건 pytest 테스트가 아니라 사전 무결성을 확인하는 독립 실행 스크립트다.
"""

import csv
import os
import re
import sys
from collections import defaultdict
from difflib import SequenceMatcher

OUT = os.path.dirname(os.path.abspath(__file__))

NON_ALNUM = re.compile(r"[^0-9A-Za-z가-힣]")


def wq_normalize(text):
    """schema.sql의 wq_normalize()와 같은 규칙."""
    return NON_ALNUM.sub("", text).lower()


def load(name):
    with open(os.path.join(OUT, name), encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


M = load("measurement_terms.csv")
D = load("metadata_terms.csv")
S = load("term_synonyms.csv")

STD = {}          # norm -> (code, std_name)
for r in M + D:
    STD[wq_normalize(r["std_name"])] = (r["code"], r["std_name"])

SYN = defaultdict(list)   # norm -> [(code, surface, source)]
for r in S:
    if r["review_status"] == "rejected":
        continue
    code = r["measurement_code"] or r["metadata_code"]
    SYN[wq_normalize(r["surface"])].append((code, r["surface"], r["source_id"]))

NAME = {r["code"]: r["std_name"] for r in M + D}


def match(surface, min_score=0.45, limit=3):
    k = wq_normalize(surface)
    out = []
    if k in STD:
        code, std = STD[k]
        out.append((code, std, "exact_standard", 1.0, std, ""))
    if k in SYN:
        for code, sfc, src in SYN[k]:
            out.append((code, NAME.get(code, "?"), "exact_synonym", 0.95, sfc, src))
    if not out:
        for nk, entries in SYN.items():
            sc = SequenceMatcher(None, nk, k).ratio()
            if sc >= min_score:
                code, sfc, src = entries[0]
                out.append((code, NAME.get(code, "?"), "fuzzy", round(sc, 3), sfc, src))
    best = {}
    for row in out:
        if row[0] not in best or row[3] > best[row[0]][3]:
            best[row[0]] = row
    return sorted(best.values(), key=lambda r: -r[3])[:limit]


# ---------------------------------------------------------------------------
failures = []


def check(cond, msg):
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        failures.append(msg)


print("=" * 78)
print("1. 사전 무결성")
print("=" * 78)

codes = {r["code"] for r in M} | {r["code"] for r in D}
orphan = [r for r in S if (r["measurement_code"] or r["metadata_code"]) not in codes]
check(not orphan, f"모든 동의어가 존재하는 표준코드를 가리킨다 (고아 {len(orphan)}건)")

norm_std = defaultdict(list)
for r in M + D:
    norm_std[wq_normalize(r["std_name"])].append(r["code"])
dup = {k: v for k, v in norm_std.items() if len(v) > 1}
check(not dup, f"표준명 정규화 키가 유일하다 (충돌 {len(dup)}건) {dup if dup else ''}")

conflict = {k: sorted({c for c, _, _ in v}) for k, v in SYN.items()
            if len({c for c, _, _ in v}) > 1}
check(not conflict,
      f"한 표기가 두 표준코드에 붙지 않는다 (충돌 {len(conflict)}건) {conflict if conflict else ''}")

no_syn = [r["code"] for r in M
          if r["review_status"] != "rejected"
          and not any((x["measurement_code"] == r["code"]) for x in S)]
print(f"  INFO  동의어가 하나도 없는 측정항목: {len(no_syn)}건 {no_syn[:12]}")

missing_src = [r for r in S if not r["source_id"] or not r["collected_on"]]
check(not missing_src, f"모든 동의어에 출처와 수집일이 있다 (누락 {len(missing_src)}건)")

tox = [r for r in M if r["is_toxic_substance"] == "True"]
check(len(tox) == 32, f"특정수질유해물질이 별표 3 기준 32종이다 (실제 {len(tox)}종)")

statutory = [r for r in M if r["legal_status"] == "statutory"]
check(len(statutory) == 57,
      f"별표 13 현행 항목이 57개다 (가목 3 + 나목 54, 실제 {len(statutory)}개)")

print()
print("=" * 78)
print("2. 실데이터 컬럼명 매칭 — 4개 기관이 BOD를 부르는 방식")
print("=" * 78)
for q in ["생화학적 산소요구량", "생물화학적산소요구량", "생물학적 산소요구량",
          "생물학적 산소요구량(BOD_L당mg)", "itemBod", "생물화학적산소요구량(BOD)"]:
    r = match(q)
    hit = r[0] if r else None
    ok = hit and hit[0] == "WQ-001"
    print(f"  {'OK ' if ok else 'MISS'}  {q:32s} -> "
          f"{hit[0] if hit else '없음':8s} {hit[2] if hit else '':15s}")
    if not ok:
        failures.append(f"BOD 매칭 실패: {q}")

print()
print("=" * 78)
print("3. 사전이 없으면 못 잡는 것들")
print("=" * 78)
tricky = [
    ("WATT", "서울시 수온. 전력(Watt)으로 오해하기 쉬운 축약"),
    ("총소질소", "안양시 CSV의 오타. 사전에 없으면 영원히 미매칭"),
    ("TOT_OC", "서울시 TOC"),
    ("itemDoc", "국립환경과학원 용존산소"),
    ("RSDLCR_ITEM_VL", "경기도 잔류염소"),
    ("MSRSTN_NM", "공통표준용어 측정소명"),
    ("1,4-다이옥세인", "환경기준 표기 (별표 13은 다이옥산)"),
    ("포름알데히드", "환경기준 표기 (별표 13은 폼알데하이드)"),
    ("6가 크롬(Cr6+)", "환경기준 표기 (별표 13은 6가크롬함유량)"),
    ("1, 1-디클로로에틸렌", "별표 3 표기 (콤마 뒤 공백)"),
]
for q, why in tricky:
    r = match(q)
    hit = r[0] if r else None
    ok = bool(hit) and hit[3] >= 0.95
    print(f"  {'OK ' if ok else 'MISS'}  {q:22s} -> {hit[0] if hit else '없음':8s} "
          f"{NAME.get(hit[0], '') if hit else '':22s} | {why}")
    if not ok:
        failures.append(f"매칭 실패: {q}")

print()
print("=" * 78)
print("4. 사전에 없는 표기 — 유사도 폴백이 후보를 내놓는가")
print("=" * 78)
unseen = ["BOD농도", "총질소(mg/L)", "수소이온농도 pH", "용존산소(DO)", "TN"]
for q in unseen:
    r = match(q)
    if r:
        c, nm, mt, sc, via, src = r[0]
        print(f"  {q:18s} -> {c:8s} {nm:20s} ({mt}, {sc}) via '{via}'")
    else:
        print(f"  {q:18s} -> 후보 없음 → unresolved_columns 큐로")

print()
print("=" * 78)
print(f"결과: {'전부 통과' if not failures else str(len(failures)) + '건 실패'}")
for f in failures:
    print("  -", f)
print("=" * 78)
sys.exit(1 if failures else 0)
