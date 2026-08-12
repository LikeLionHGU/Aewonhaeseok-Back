"""실데이터 인코딩 회귀 테스트.

왜 필요한가:
매핑 엔진의 테스트 40개는 픽스처가 전부 .xlsx다. 그런데 실제 데이터는 전부 CSV이고
공공기관 파일은 cp949가 태반이다. 즉 config.CSV_ENCODINGS 폴백 경로
(utf-8-sig → cp949 → euc-kr)가 한 번도 검증된 적이 없다.

운영에서 가장 먼저 깨질 자리라 여기서 실파일로 막는다.

    python -m pytest backend/mapper_service/tests/ -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SERVICE_DIR = REPO_ROOT / "backend" / "mapper_service"
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

from app import detect_encoding, summarize_values  # noqa: E402
from pipeline import config  # noqa: E402
from pipeline.mapper import AUTO_STATUSES, load_lexicon, map_file, read_data_file  # noqa: E402

SAMPLES = REPO_ROOT / "data" / "samples"
HOLDOUT = REPO_ROOT / "data" / "holdout"


def real_files() -> list[Path]:
    files = sorted(SAMPLES.glob("*.csv")) + sorted(HOLDOUT.glob("*.csv"))
    if not files:
        pytest.skip("실데이터가 없다 (data/samples, data/holdout)")
    return files


@pytest.fixture(scope="session")
def lexicon():
    return load_lexicon(
        REPO_ROOT / config.ONTOLOGY_DIR / config.MEASUREMENT_DICT_FILENAME,
        REPO_ROOT / config.ONTOLOGY_DIR / config.METADATA_DICT_FILENAME,
    )


# ═══════════════════════════════════════════════════════════════════
# 인코딩
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("path", real_files(), ids=lambda p: p.stem)
def test_실파일이_읽힌다(path: Path):
    """엔진이 실데이터 CSV를 인코딩 폴백으로 읽어낸다."""
    df, header_row = read_data_file(path)
    assert len(df.columns) > 0
    assert header_row >= 0


@pytest.mark.parametrize("path", real_files(), ids=lambda p: p.stem)
def test_인코딩이_판별된다(path: Path):
    """어느 인코딩으로 읽혔는지 알아낼 수 있다. 화면에 표시할 값이다."""
    encoding = detect_encoding(path)
    assert encoding in config.CSV_ENCODINGS, f"{path.name}: 판별 실패"


@pytest.mark.parametrize("path", real_files(), ids=lambda p: p.stem)
def test_한글_컬럼명이_깨지지_않는다(path: Path):
    """인코딩을 잘못 잡으면 컬럼명이 깨진다. 깨지면 매핑이 통째로 실패한다.

    한글이 제대로 디코딩됐는지는 완성형 한글 음절이 실제로 들어 있는지로 본다.
    cp949 파일을 latin-1로 읽으면 이 글자들이 나오지 않는다.
    """
    df, _ = read_data_file(path)
    joined = "".join(str(c) for c in df.columns)
    hangul = sum(1 for ch in joined if "가" <= ch <= "힣")
    assert hangul > 0, f"{path.name}: 컬럼명에 한글이 없다 — 인코딩이 깨졌을 가능성"


def test_cp949_파일이_실제로_있다():
    """이 테스트 자체가 의미 있으려면 cp949 파일이 표본에 있어야 한다.

    전부 UTF-8이면 폴백 경로를 검증한 것이 아니다.
    """
    encodings = {detect_encoding(p) for p in real_files()}
    assert "cp949" in encodings or "euc-kr" in encodings, (
        f"표본에 한국어 레거시 인코딩 파일이 없다: {encodings}")


def test_인코딩을_못_읽는_파일은_실패한다(tmp_path: Path):
    """읽을 수 없는 파일을 조용히 통과시키지 않는다."""
    broken = tmp_path / "broken.csv"
    # 어떤 인코딩으로도 디코딩되지 않는 바이트열
    broken.write_bytes(b"\xff\xfe\x00\x80\x81\xfd\xfc")
    assert detect_encoding(broken) is None


# ═══════════════════════════════════════════════════════════════════
# 매핑률 회귀
# ═══════════════════════════════════════════════════════════════════

# 2026-08-11, dict-2026-08-10 기준 실측값.
# 사전을 고친 뒤 이 숫자가 떨어지면 회귀다. 올라가면 기대값을 갱신한다.
EXPECTED_AUTO_RATE = {
    "김해시_하천수질현황": 100.0,
    "부산시_약수터_수질검사": 91.7,
    "안양시_안양천_수질측정정보": 100.0,
    "인천시_수질오염": 99.0,
    "전북_보건환경연구원_하천수질측정망": 100.0,
    "제주_하천수질조사결과": 94.1,
    "충남_보건환경연구원_물환경측정망_하천": 87.0,
}


@pytest.mark.parametrize("path", real_files(), ids=lambda p: p.stem)
def test_자동_매핑률이_떨어지지_않는다(path: Path, lexicon):
    """사전을 고쳤을 때 기존 성능이 나빠지지 않았는지 본다.

    매핑 엔진 저장소에는 실데이터 기준 회귀 테스트가 없어서, 사전을 고쳐도
    성능이 떨어지는 것을 아무도 알려주지 않는다. 그 자리를 여기서 메운다.
    """
    expected = EXPECTED_AUTO_RATE.get(path.stem)
    if expected is None:
        pytest.skip(f"{path.stem}: 기대값이 등록되지 않았다")

    mapping = map_file(path, lexicon)
    total = len(mapping.results)
    auto = sum(1 for r in mapping.results if r.status in AUTO_STATUSES)
    rate = round(100.0 * auto / total, 1)

    assert rate >= expected, (
        f"{path.name}: 자동 매핑률이 {expected}% → {rate}% 로 떨어졌다")


def test_exact_판정에는_점수가_없다(lexicon):
    """사전에 그대로 있었다는 뜻이지 유사도 100점이 아니다.

    화면이 이 값을 '100점'으로 표시하면 안 되므로 계약으로 못박는다.
    """
    mapping = map_file(SAMPLES / "제주_하천수질조사결과.csv", lexicon)
    exact = [r for r in mapping.results if r.status == "exact"]
    assert exact, "exact 판정이 하나도 없다 — 표본이 잘못됐다"
    assert all(r.score is None for r in exact)


# ═══════════════════════════════════════════════════════════════════
# 값 요약
# ═══════════════════════════════════════════════════════════════════

def test_같은_컬럼명이라도_값이_다르면_구분된다(lexicon):
    """검증 화면에 실제 값을 함께 보여줘야 하는 이유.

    '구분'이라는 같은 컬럼명이 인천에서는 날짜, 제주에서는 분기를 가리킨다.
    컬럼명만 보여주면 사람도 판정할 수 없다.
    """
    def summary_of(filename: str, column_name: str) -> dict:
        mapping = map_file(SAMPLES / filename, lexicon)
        index = next(i for i, r in enumerate(mapping.results) if r.raw == column_name)
        return summarize_values(mapping.mapped_df.iloc[:, index])

    incheon = summary_of("인천시_수질오염.csv", "구분")
    jeju = summary_of("제주_하천수질조사결과.csv", "구분")

    assert incheon["samples"], "인천 '구분'에 값이 없다"
    assert jeju["samples"], "제주 '구분'에 값이 없다"
    assert incheon["samples"] != jeju["samples"], (
        "같은 컬럼명인데 값 요약이 같다면 검증 화면이 둘을 구분해줄 수 없다")
