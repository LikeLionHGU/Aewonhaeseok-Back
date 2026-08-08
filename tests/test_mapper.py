from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from pipeline import config
from pipeline.mapper import (
    STATUS_EXACT,
    STATUS_FUZZY_AUTO,
    STATUS_NEEDS_REVIEW,
    STATUS_UNMAPPED,
    DictionaryConflictError,
    llm_fallback,
    load_lexicon,
    map_column,
    map_file,
    normalize,
    output_column_name,
    read_data_file,
)
from pipeline.run import run as run_pipeline


# ── 0단계: 정규화 ─────────────────────────────────────────────────────────

def test_normalize_keeps_raw_and_strips_separators():
    n = normalize("  총_질-소  ")
    assert n.raw == "  총_질-소  "   # 원본은 절대 버리지 않는다
    assert n.body == "총질소"


def test_normalize_separates_paren_and_extracts_abbr():
    n = normalize("생물학적 산소요구량(BOD_L당mg)")
    assert n.body == "생물학적산소요구량"
    assert "bod" in n.paren_tokens          # 괄호부에서 약어 추출
    assert "l당mg" not in n.paren_tokens    # 단위 표기는 토큰에서 제거


def test_normalize_drops_unit_only_paren_and_fullwidth():
    n = normalize("수온（℃）")               # 전각 괄호 + 단위만 있는 괄호부
    assert n.body == "수온"
    assert n.paren_tokens == ()


def test_normalize_strips_trailing_units():
    assert normalize("총유기탄소 mg/L").body == "총유기탄소"
    assert normalize("탁도NTU").body == "탁도"


# ── 1단계: 사전 정확 일치 ─────────────────────────────────────────────────

@pytest.mark.parametrize("name,code", [
    ("총질소", "WQ-TN"),
    ("T-N", "WQ-TN"),
    ("itemBod", "WQ-BOD"),
    ("측정소명", "MD-PTNM"),
    ("측정일시", "MD-DATE"),
])
def test_exact_match(lexicon, name, code):
    r = map_column(name, lexicon)
    assert r.status == STATUS_EXACT
    assert r.code == code
    assert r.score is None  # exact는 점수 없음 — 판단은 사전이 한다


def test_exact_records_dict_type(lexicon):
    assert map_column("총질소", lexicon).dict_type == "측정항목"
    assert map_column("측정소명", lexicon).dict_type == "메타"


def test_paren_abbr_routes_to_exact(lexicon):
    """단위 붙은 변형: 본체는 사전에 없어도 괄호 약어(BOD) 경유로 exact."""
    r = map_column("생물학적 산소요구량(BOD_L당mg)", lexicon)
    assert r.status == STATUS_EXACT
    assert r.code == "WQ-BOD"
    assert r.via == "paren"


def test_conflicting_dictionaries_raise(tmp_path: Path):
    """같은 표기가 두 사전에 모두 있으면 숨기지 말고 에러."""
    cols_m = ["code", "name_ko", "name_en", "abbr", "synonyms",
              "unit", "category", "legal_basis", "verified", "note"]
    cols_d = ["code", "name_ko", "name_en", "abbr", "synonyms",
              "unit", "category", "reference", "verified", "note"]
    pd.DataFrame([["WQ-X", "총질소", "", "", "", "", "", "", "Y", ""]], columns=cols_m) \
        .to_csv(tmp_path / "m.csv", index=False)
    pd.DataFrame([["MD-X", "총질소", "", "", "", "", "", "", "Y", ""]], columns=cols_d) \
        .to_csv(tmp_path / "d.csv", index=False)
    with pytest.raises(DictionaryConflictError):
        load_lexicon(tmp_path / "m.csv", tmp_path / "d.csv")


# ── 1.5단계: 복합 컬럼명 분해 ────────────────────────────────────────────
#
# 인천시 파일처럼 하천명이 컬럼명에 병합된 wide 구조를 다룬다.
# 이 규칙이 없으면 사전에 정확히 있는 항목까지 지점명 때문에 유사도가 깎여
# needs_review로 떨어진다 (실측: 인천 97컬럼 중 자동매핑 12.4%).

@pytest.mark.parametrize("name, code, site", [
    ("공촌천_수온", "WQ-TEMP", "공촌천"),
    ("굴포천_수소이온농도", "WQ-PH", "굴포천"),
    ("학익배수구_부유물질", "WQ-SS", "학익배수구"),
    # 구분자가 빠진 표기 — 구분자 위치를 믿고 자르면 놓친다
    ("시천천_심곡천수온", "WQ-TEMP", "시천천심곡천"),
    # 구분자가 엉뚱한 자리에 붙은 원본 오타 — 지점 라벨이 정상 표기로 병합돼야 한다
    ("나진포_천부유물질", "WQ-SS", "나진포천"),
])
def test_composite_splits_site_prefix(lexicon, name, code, site):
    r = map_column(name, lexicon)
    assert r.status == STATUS_EXACT      # 사전 exact 일치이므로 자동 매핑에 포함된다
    assert r.via == "composite"
    assert r.code == code
    assert r.site == site
    assert r.score is None               # 유사도를 쓰지 않았으므로 점수가 없어야 한다


def test_composite_does_not_shadow_whole_name_exact(lexicon):
    """접두어 없는 이름은 1단계에서 끝나야 한다. 분해가 먼저 돌면 안 된다."""
    r = map_column("수온", lexicon)
    assert r.status == STATUS_EXACT
    assert r.via == "body"
    assert r.site is None


@pytest.mark.parametrize("name", ["공촌천", "학익배수구", "측정지점_알수없는항목"])
def test_composite_does_not_force_match(lexicon, name):
    """꼬리가 사전에 exact로 없으면 분해가 억지로 코드를 붙이면 안 된다."""
    r = map_column(name, lexicon)
    assert r.via != "composite"
    assert r.site is None


def test_composite_output_keeps_sites_distinct(lexicon):
    """지점만 다른 같은 항목이 출력에서 겹치면 데이터가 조용히 덮인다."""
    a = map_column("공촌천_수온", lexicon)
    b = map_column("굴포천_수온", lexicon)
    assert a.code == b.code == "WQ-TEMP"
    assert output_column_name(a) == f"WQ-TEMP{config.SITE_SEPARATOR}공촌천"
    assert output_column_name(b) == f"WQ-TEMP{config.SITE_SEPARATOR}굴포천"
    assert output_column_name(a) != output_column_name(b)


def test_mapped_columns_are_unique(project, lexicon):
    """어떤 입력이 와도 출력 컬럼명은 유일해야 한다 (중복은 일련번호로 분리)."""
    for path in sorted((project / "data" / "samples").iterdir()):
        cols = list(map_file(path, lexicon).mapped_df.columns)
        assert len(cols) == len(set(cols)), f"{path.name}: 컬럼명 중복 {cols}"


# ── 2단계: 유사도 후보 ───────────────────────────────────────────────────

def test_typo_caught_by_fuzzy(lexicon):
    """오타 '총소질소' → 총질소 후보. fuzzy_auto 또는 needs_review여야 한다."""
    r = map_column("총소질소", lexicon)
    assert r.status in (STATUS_FUZZY_AUTO, STATUS_NEEDS_REVIEW)
    assert (r.code or r.candidate_code) == "WQ-TN"
    assert r.score is not None and r.score >= config.FUZZY_REVIEW_THRESHOLD


@pytest.mark.parametrize("name", ["WATT", "FACLT_NM"])
def test_unrelated_columns_stay_unmapped(lexicon, name):
    """문자열 무관 케이스는 억지로 잡으면 안 된다 → unmapped."""
    r = map_column(name, lexicon)
    assert r.status == STATUS_UNMAPPED
    assert r.code is None and r.candidate_code is None


# ── 헤더 자동 탐지 ───────────────────────────────────────────────────────

def test_header_detected_on_second_row(project):
    df, header_row = read_data_file(project / "data" / "samples" / "test3_header_row2.xlsx")
    assert header_row == 1
    assert list(df.columns) == ["측정소코드", "T-N", "총인", "수온(℃)"]
    assert len(df) == 2


def test_header_detected_on_first_row(project):
    _, header_row = read_data_file(project / "data" / "samples" / "test1_exact.xlsx")
    assert header_row == 0


# ── 병합 헤더 복원 ───────────────────────────────────────────────────────
#
# 충남 물환경측정망 파일에서 발견: 지점명·지점번호가 1행에 세로 병합돼 있어
# 2행을 헤더로 고르면 그 두 컬럼이 통째로 UNNAMED로 소실됐다.

def _write_merged_header_file(path: Path) -> None:
    """1행 그룹 헤더 + 2행 세부 헤더. 앞 두 칸은 세로 병합(2행이 빈칸).

    실제 파일이 그렇듯 그룹 라벨(3개)이 세부 라벨(4개)보다 적어야
    detect_header_row가 2행을 헤더로 고른다.
    """
    pd.DataFrame([
        ["측정소명", "측정소코드", "측정값", None,   None,   None],
        [None,       None,         "총질소", "총인", "수온", "pH"],
        ["가평-1",   "S001",       2.1,      0.04,   18.2,   7.2],
    ]).to_excel(path, index=False, header=False)


def test_merged_header_recovers_vertically_merged_cells(tmp_path: Path, lexicon):
    p = tmp_path / "merged.xlsx"
    _write_merged_header_file(p)
    df, header_row = read_data_file(p)

    assert header_row == 1
    # 빈칸은 위 행에서 끌어오고, 값이 있는 칸은 그대로 둔다
    assert list(df.columns) == ["측정소명", "측정소코드", "총질소", "총인", "수온", "pH"]
    assert not any(c.startswith(config.UNMAPPED_PREFIX) or c.startswith("UNNAMED")
                   for c in df.columns)
    # 복원된 컬럼이 실제로 매핑까지 되어야 의미가 있다
    assert map_column(df.columns[0], lexicon).code == "MD-PTNM"


def test_merged_header_does_not_absorb_title_row(project):
    """제목 한 줄(셀 1개)은 그룹 헤더가 아니므로 끌어오면 안 된다."""
    df, header_row = read_data_file(project / "data" / "samples" / "test3_header_row2.xlsx")
    assert header_row == 1
    assert list(df.columns) == ["측정소코드", "T-N", "총인", "수온(℃)"]
    assert not any("결과보고" in c for c in df.columns)


# ── 사전 버전 ────────────────────────────────────────────────────────────

def test_version_hash_tracks_content_not_mtime(tmp_path: Path):
    """같은 내용을 다시 써도 해시가 같아야 불필요한 리로드를 안 한다."""
    from pipeline.version import compute_content_hash

    a, b = tmp_path / "m.csv", tmp_path / "d.csv"
    a.write_text("code,name_ko\nWQ-001,BOD\n", encoding="utf-8")
    b.write_text("code,name_ko\nMD-001,측정소명\n", encoding="utf-8")
    first = compute_content_hash(a, b)

    a.write_text("code,name_ko\nWQ-001,BOD\n", encoding="utf-8")   # 내용 동일
    assert compute_content_hash(a, b) == first

    a.write_text("code,name_ko\nWQ-001,BOD5\n", encoding="utf-8")  # 내용 변경
    assert compute_content_hash(a, b) != first


def test_version_roundtrip_and_staleness(tmp_path: Path):
    from pipeline.version import (
        VERSION_FILENAME,
        VersionFileMissing,
        build_version,
        is_stale,
        load_dictionary_version,
        write_version,
    )

    onto = tmp_path / "ontology"
    onto.mkdir()
    m, d = onto / "measurement_terms.csv", onto / "metadata_terms.csv"
    m.write_text("code\nWQ-001\n", encoding="utf-8")
    d.write_text("code\nMD-001\n", encoding="utf-8")

    with pytest.raises(VersionFileMissing):
        load_dictionary_version(onto)

    v = build_version(m, d, measurement_terms=1, metadata_terms=1,
                      synonyms=0, verified_terms=1, today=date(2026, 8, 8))
    write_version(onto / VERSION_FILENAME, v)

    loaded = load_dictionary_version(onto)
    assert loaded.version == "dict-2026-08-08"      # git 태그와 같은 규칙
    assert loaded.content_hash == v.content_hash
    assert loaded.as_dict()["counts"]["measurement_terms"] == 1
    assert not is_stale(loaded, onto)

    # 사전이 바뀌고 다시 내보내면 낡은 것으로 감지돼야 한다
    m.write_text("code\nWQ-001\nWQ-002\n", encoding="utf-8")
    write_version(onto / VERSION_FILENAME,
                  build_version(m, d, measurement_terms=2, metadata_terms=1,
                                synonyms=0, verified_terms=1, today=date(2026, 8, 8)))
    assert is_stale(loaded, onto)


def test_shipped_version_matches_current_dictionary():
    """저장소에 커밋된 VERSION.json이 지금 사전과 맞는가.

    사전을 고치고 export를 빠뜨리면 백엔드가 낡은 버전을 표시하게 된다.
    """
    from pipeline.version import compute_content_hash, load_dictionary_version

    onto = Path(__file__).resolve().parents[1] / "ontology"
    v = load_dictionary_version(onto)
    actual = compute_content_hash(onto / "measurement_terms.csv",
                                  onto / "metadata_terms.csv")
    assert v.content_hash == actual, (
        "VERSION.json이 현재 사전과 다릅니다. "
        "python3 ontology/export_ontology.py 를 다시 돌리세요."
    )


# ── 3단계: LLM fallback 훅 ──────────────────────────────────────────────

def test_llm_fallback_is_stub(lexicon):
    with pytest.raises(NotImplementedError):
        llm_fallback("정체불명컬럼", lexicon)


# ── 엔드투엔드 ───────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def e2e_report(project):
    output = project / "output"
    report = run_pipeline(project / "data" / "samples", project / "ontology", output)
    return project, output, report


def test_e2e_outputs_exist(e2e_report):
    project, output, _ = e2e_report
    assert (output / "report.json").exists()
    assert (output / "review_queue.csv").exists()
    for stem in ("test1_exact", "test2_variants", "test3_header_row2"):
        assert (output / "mapped" / f"{stem}_mapped.csv").exists()


def test_e2e_report_summary(e2e_report):
    _, output, report = e2e_report
    saved = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert saved["summary"] == report["summary"]
    s = report["summary"]
    assert s["파일 수"] == 3
    assert s["전체 컬럼 수"] == 14
    # 실패는 WATT, FACLT_NM 단 2건이어야 한다
    n_unmapped = sum(
        1 for f in report["files"] for c in f["columns"] if c["결과"] == STATUS_UNMAPPED
    )
    assert n_unmapped == 2
    assert s["실패율"] == round(100.0 * 2 / 14, 1)


def test_e2e_watt_is_unmapped_not_review(e2e_report):
    """완료 조건: WATT가 needs_review/fuzzy로 잡히면 임계값이 잘못된 것."""
    _, _, report = e2e_report
    results = {c["원본명"]: c["결과"] for f in report["files"] for c in f["columns"]}
    assert results["WATT"] == STATUS_UNMAPPED
    assert results["FACLT_NM"] == STATUS_UNMAPPED


def test_e2e_mapped_csv_columns(e2e_report):
    project, output, _ = e2e_report
    m2 = pd.read_csv(output / "mapped" / "test2_variants_mapped.csv", encoding="utf-8-sig")
    cols = list(m2.columns)
    assert "MD-PTNM" in cols                       # 측정소명 → 코드 치환
    assert "WQ-BOD" in cols                        # 괄호 약어 경유 exact
    assert f"{config.UNMAPPED_PREFIX}WATT" in cols  # unmapped는 원본명 + 접두어
    assert f"{config.UNMAPPED_PREFIX}FACLT_NM" in cols


def test_e2e_review_queue_contents(e2e_report):
    _, output, report = e2e_report
    q = pd.read_csv(output / "review_queue.csv", encoding="utf-8-sig")
    assert list(q.columns) == ["원본명", "출처파일", "후보 표준코드", "점수", "사람판정", "판정자"]
    names = set(q["원본명"])
    assert {"WATT", "FACLT_NM"} <= names
    # needs_review/unmapped가 아닌 컬럼은 대기열에 없어야 한다
    adopted = {
        c["원본명"] for f in report["files"] for c in f["columns"]
        if c["결과"] in (STATUS_EXACT, STATUS_FUZZY_AUTO)
    }
    assert names.isdisjoint(adopted)


# ── apply_review ─────────────────────────────────────────────────────────

def test_apply_review_adds_synonym(project, e2e_report, tmp_path):
    from pipeline.apply_review import apply_review
    import shutil

    _, output, _ = e2e_report
    ontology = tmp_path / "ontology"
    shutil.copytree(project / "ontology", ontology)

    q = pd.read_csv(output / "review_queue.csv", encoding="utf-8-sig", dtype=str).fillna("")
    q.loc[q["원본명"] == "FACLT_NM", ["사람판정", "판정자"]] = ["MD-PTNM", "박서연"]
    queue_path = tmp_path / "review_queue_filled.csv"
    q.to_csv(queue_path, index=False, encoding="utf-8-sig")

    log = apply_review(queue_path, ontology)

    meta = pd.read_csv(ontology / "metadata_terms.csv", dtype=str).fillna("")
    syn = meta.loc[meta["code"] == "MD-PTNM", "synonyms"].iloc[0]
    assert "FACLT_NM" in syn.split("|")
    assert len(log) == 1
    assert log.iloc[0]["source"] == "test2_variants.xlsx"
    assert log.iloc[0]["reviewer"] == "박서연"
    assert log.iloc[0]["collected_at"]  # 수집 시각 기록

    # 반영 후에는 exact로 잡혀야 한다
    lex = load_lexicon(ontology / "measurement_terms.csv", ontology / "metadata_terms.csv")
    r = map_column("FACLT_NM", lex)
    assert r.status == STATUS_EXACT and r.code == "MD-PTNM"
