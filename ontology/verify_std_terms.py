"""메타 사전의 미확인(UNCHECKED) 행을 행안부 공공데이터 공통표준용어와 대조한다.

  python3 ontology/verify_std_terms.py <표준용어.csv> [--words <표준단어.csv>]

필요한 파일 (공공데이터포털에서 사람이 직접 받는다):
  · 공통표준용어  https://www.data.go.kr/data/15156379/fileData.do
  · 공통표준단어  같은 포털에서 '공공데이터 공통표준단어'로 검색 (--words 로 전달)

──────────────────────────────────────────────────────────────────────────
검증이란 무엇인가 — 유사도는 검증이 아니다
──────────────────────────────────────────────────────────────────────────
유사도 점수는 "글자가 비슷하다"만 말한다. 근거가 될 수 없다.
이 스크립트는 근거가 되는 세 가지를 순서대로 확인한다.

  1) 정확 일치      표준용어 목록에 그 이름이 그대로 있는가
  2) 이음동의어     '용어 이음동의어 목록'에 그 이름이 등재돼 있는가
                    (→ 표준용어명과 다른 표기로 이미 인정된 경우를 잡는다)
  3) 포함 관계      그 이름을 포함하거나, 그 이름에 포함되는 표준용어가 있는가
                    (→ 다른 이름으로 등재돼 있을 가능성을 잡는다)
  4) 표준단어 분해  이름 전체가 표준단어들로 쪼개지는가
                    (→ 행안부 표준은 '표준단어 조합 + 도메인 접미사' 규칙이라,
                       분해되면 적법한 기관표준용어라고 말할 수 있다)

유사도는 맨 마지막에 참고로만 출력한다. 이 점수로 판정하지 말 것.

──────────────────────────────────────────────────────────────────────────
결과를 어떻게 기록하는가
──────────────────────────────────────────────────────────────────────────
확인한 사실만 쓴다. "아마 그럴 것이다"는 쓰지 않는다.

  1)이 맞으면   basis = "공공데이터 공통표준용어(행정안전부, 20251101 8차)"
                review = "verified"
  2)가 맞으면   basis = "공공데이터 공통표준용어 이음동의어(행정안전부, 20251101 8차) — 표준용어명 '<정식명>'"
                review = "verified"
  3)만 맞으면   basis = "공통표준용어 '<찾은 용어>' 차용"   ← MD-030이 쓴 방식
                review = "verified", note에 왜 그대로 쓰지 않았는지 적는다
  4)만 맞으면   basis = "공통표준용어 미등재 — 공통표준단어 조합(기관표준용어)"
                review = "verified", note에 분해 결과를 적는다 (예: 측정+시설+명)
  전부 아니면   basis = "공통표준용어·표준단어 미등재 — 소스 관행"
                review = "draft" 유지, note에 대조일과 확인 사실을 적는다

마지막 경우도 '검증 완료'다. 목표는 전부 verified로 만드는 게 아니라
'미확인'이라는 상태를 없애는 것이다. 확인해서 없더라는 것도 확인이다.

수정 후 실행:
  python3 ontology/source/build_dictionary.py
  python3 ontology/source/check_dictionary.py
  python3 ontology/export_ontology.py
  python3 -m pytest -q
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

HERE = Path(__file__).resolve().parent
META_SOURCE = HERE / "source" / "metadata_terms.csv"

ENCODINGS = ("utf-8-sig", "cp949", "euc-kr")
FUZZY_TOP_N = 3


def read_any(path: Path) -> pd.DataFrame:
    for enc in ENCODINGS:
        try:
            return pd.read_csv(path, dtype=str, encoding=enc).fillna("")
        except (UnicodeDecodeError, ValueError):
            continue
    raise SystemExit(f"CSV 인코딩을 인식하지 못했습니다: {path}")


def pick_column(df: pd.DataFrame, must: str, avoid: tuple[str, ...] = ("영문",)) -> str:
    cands = [c for c in df.columns if must in c and not any(a in c for a in avoid)]
    if not cands:
        raise SystemExit(f"'{must}' 컬럼을 찾지 못했습니다. 실제 컬럼: {list(df.columns)}")
    return cands[0]


def decompose(term: str, words: set[str], max_word_len: int) -> list[str] | None:
    """용어를 표준단어들로 완전 분해한다. 불가능하면 None.

    긴 단어를 우선 매칭하고, 막히면 되돌아간다(백트래킹).
    '측정시설명' → ['측정', '시설', '명']

    ⚠️ 분해 성공은 '글자가 맞는다'까지만 말한다. 각 단어의 한자·설명을 반드시 눈으로
    확인할 것 — 표준단어 '지점'은 支店(본점에서 갈라진 점포)이지 측정 地點이 아니다.
    地點 계열은 '측정지점' MSPT, '관측지점' OBSPT로 따로 등재돼 있다.
    """
    if not term:
        return []
    for size in range(min(max_word_len, len(term)), 0, -1):
        head = term[:size]
        if head in words:
            rest = decompose(term[size:], words, max_word_len)
            if rest is not None:
                return [head] + rest
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description="메타 사전 미확인 행을 공통표준용어와 대조")
    ap.add_argument("terms", help="공공데이터 공통표준용어 CSV")
    ap.add_argument("--words", help="공공데이터 공통표준단어 CSV (있으면 분해 검증 수행)")
    args = ap.parse_args()

    std = read_any(Path(args.terms))
    term_col = pick_column(std, "용어명")
    desc_col = next((c for c in std.columns if "설명" in c), None)
    names = std[term_col].str.strip()
    name_list = names.tolist()
    name_set = set(name_list)
    print(f"공통표준용어 {len(std):,}건 로딩 (용어명 컬럼: {term_col})")

    words: set[str] = set()
    word_abbr: dict[str, str] = {}
    word_desc: dict[str, str] = {}
    max_word_len = 0
    if args.words:
        wdf = read_any(Path(args.words))
        word_col = pick_column(wdf, "단어명")
        # 폐기된 단어는 조합에 쓸 수 없다
        rev_col = next((c for c in wdf.columns if "개정구분" in c), None)
        if rev_col is not None:
            dropped = (wdf[rev_col].str.strip() == "폐기").sum()
            wdf = wdf[wdf[rev_col].str.strip() != "폐기"]
            if dropped:
                print(f"  (폐기 단어 {dropped}개 제외)")
        abbr_col = next((c for c in wdf.columns if "단어영문약어명" in c), None)
        desc_col_w = next((c for c in wdf.columns if "단어 설명" in c or "단어설명" in c), None)
        for _, w in wdf.iterrows():
            name = str(w[word_col]).strip()
            if not name:
                continue
            words.add(name)
            word_abbr[name] = str(w[abbr_col]).strip() if abbr_col else ""
            word_desc[name] = str(w[desc_col_w]).strip() if desc_col_w else ""
        max_word_len = max(len(w) for w in words) if words else 0
        print(f"공통표준단어 {len(words):,}건 로딩 (단어명 컬럼: {word_col})")
    else:
        print("⚠️  표준단어 파일이 없습니다. --words 를 주면 분해 검증까지 합니다.")

    meta = read_any(META_SOURCE)
    targets = meta[meta["standard_basis"].str.contains("미확인", na=False)]
    print(f"\n대조 대상: 미확인 {len(targets)}행")
    print("=" * 72)

    # 이음동의어 색인: 표기 → 정식 표준용어명
    syn_col = next((c for c in std.columns if "이음동의어" in c), None)
    syn_index: dict[str, str] = {}
    if syn_col:
        for _, r in std.iterrows():
            for s in str(r[syn_col]).split(","):
                s = s.strip()
                if s:
                    syn_index.setdefault(s, r[term_col].strip())
        print(f"이음동의어 {len(syn_index):,}개 색인 (컬럼: {syn_col})")

    summary = {"등재": [], "이음동의어": [], "차용": [], "조합": [], "미등재": []}

    for _, row in targets.iterrows():
        term = row["std_name"].strip()
        print(f"\n■ {row['code']}  {term}")

        # 1) 정확 일치
        if term in name_set:
            hit = std[names == term].iloc[0]
            desc = hit[desc_col] if desc_col else ""
            print(f"  ✅ 1) 정확 일치 — 표준용어에 등재됨")
            print(f"       설명: {desc[:70]}")
            print(f"  → basis = 공공데이터 공통표준용어(행정안전부, 20251101 8차) / review = verified")
            summary["등재"].append(term)
            continue

        print("  · 1) 정확 일치: 없음")

        # 2) 이음동의어 일치
        if term in syn_index:
            official = syn_index[term]
            print(f"  ✅ 2) 이음동의어로 등재됨 — 정식 표준용어명: {official}")
            print(f"  → basis = 공공데이터 공통표준용어 이음동의어(…8차) — 표준용어명 '{official}' / review = verified")
            summary["이음동의어"].append(f"{term}→{official}")
            continue

        if syn_col:
            print("  · 2) 이음동의어: 없음")

        # 3) 포함 관계 (양방향)
        contains = [n for n in name_list if n and n != term and (n in term or term in n)]
        contains = sorted(set(contains), key=len, reverse=True)[:6]
        if contains:
            print("  · 3) 포함 관계 있는 표준용어:")
            for c in contains:
                d = std.loc[names == c, desc_col].iloc[0] if desc_col else ""
                print(f"       {c}  |  {d[:50]}")
        else:
            print("  · 3) 포함 관계: 없음")

        # 3) 표준단어 분해
        parts = decompose(term, words, max_word_len) if words else None
        if parts:
            combo = "_".join(word_abbr.get(p, "?") for p in parts)
            print(f"  ✅ 4) 표준단어로 분해됨: {' + '.join(parts)}   조합약어 {combo}")
            print(f"     ⚠️ 각 단어의 뜻이 우리 개념과 맞는지 확인할 것 (분해 성공 ≠ 의미 일치):")
            for p in parts:
                print(f"        {p} → {word_abbr.get(p, '?'):10} | {word_desc.get(p, '')[:56]}")
            print(f"  → 뜻이 맞으면: basis = 공통표준용어 미등재 — 공통표준단어 조합(기관표준용어)")
            print(f"     review = verified, abbr = {combo}, note에 분해 결과를 남길 것")
            print(f"     뜻이 어긋나는 단어가 하나라도 있으면 조합 판정을 쓰지 말 것")
            summary["조합"].append(term)
        elif words:
            print("  ✗ 4) 표준단어로 분해되지 않음")
            print(f"  → basis = 공통표준용어·표준단어 미등재 — 소스 관행 / review = draft 유지")
            summary["미등재"].append(term)
        else:
            print("  · 4) 표준단어 분해: 미수행 (--words 필요)")

        # 참고: 유사도 (근거 아님)
        found = process.extract(term, name_list, scorer=fuzz.ratio, limit=FUZZY_TOP_N)
        cands = ", ".join(f"{c}({s:.0f})" for c, s, _ in found)
        print(f"  · 참고 유사도(근거 아님): {cands}")

    print("\n" + "=" * 72)
    print("판정 요약")
    for k, v in summary.items():
        if v:
            print(f"  {k} {len(v)}건: {', '.join(v)}")
    print("\n확인 결과는 source/build_dictionary.py에 기록할 것.")
    print("reviewed_by(이름)와 reviewed_at(대조한 날짜)도 함께 채운다.")


if __name__ == "__main__":
    main()
