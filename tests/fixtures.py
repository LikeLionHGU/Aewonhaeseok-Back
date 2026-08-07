"""테스트용 fixture 생성기.

실데이터·운영 사전 없이도 pytest가 통과해야 하므로,
테스트 전용의 소형 표준 사전 2개와 테스트 엑셀 3개를 임시 디렉토리에 만들어 쓴다.
운영 ontology/ 디렉토리는 건드리지 않는다.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

MEASUREMENT_ROWS = [
    # code, name_ko, name_en, abbr, synonyms, unit, category, legal_basis, verified, note
    ["WQ-BOD", "생물화학적산소요구량", "Biochemical Oxygen Demand", "BOD", "BOD5|itemBod",
     "mg/L", "유기물", "환경정책기본법 시행령 별표1", "Y", ""],
    ["WQ-COD", "화학적산소요구량", "Chemical Oxygen Demand", "COD", "CODMn|itemCod",
     "mg/L", "유기물", "환경정책기본법 시행령 별표1", "Y", ""],
    ["WQ-TN", "총질소", "Total Nitrogen", "T-N", "TN|itemTn",
     "mg/L", "영양염류", "환경정책기본법 시행령 별표1", "Y", ""],
    ["WQ-TP", "총인", "Total Phosphorus", "T-P", "TP|itemTp",
     "mg/L", "영양염류", "환경정책기본법 시행령 별표1", "Y", ""],
    ["WQ-PH", "수소이온농도", "Hydrogen Ion Concentration", "pH", "PH|itemPh",
     "", "일반", "환경정책기본법 시행령 별표1", "Y", ""],
    ["WQ-SS", "부유물질", "Suspended Solids", "SS", "부유물질량|itemSs",
     "mg/L", "일반", "환경정책기본법 시행령 별표1", "Y", ""],
    ["WQ-TEMP", "수온", "Water Temperature", "TEMP", "WTEMP|itemTemp",
     "℃", "일반", "수질오염공정시험기준", "Y", ""],
]
MEASUREMENT_COLUMNS = ["code", "name_ko", "name_en", "abbr", "synonyms",
                       "unit", "category", "legal_basis", "verified", "note"]

METADATA_ROWS = [
    ["MD-PTNO", "측정소코드", "Station Code", "PT_NO", "측정소ID|측정지점코드|ptNo",
     "", "관측지점", "공공데이터 공통표준용어", "Y", ""],
    ["MD-PTNM", "측정소명", "Station Name", "PT_NM", "측정소이름|측정지점명|ptNm",
     "", "관측지점", "공공데이터 공통표준용어", "Y", ""],
    ["MD-DATE", "측정일시", "Measurement Datetime", "MSR_DT", "측정일자|측정일|측정연월일|wmcymd",
     "", "시간", "KS X ISO 8601", "Y", ""],
    ["MD-LAT", "위도", "Latitude", "LAT", "위도좌표|latDgr",
     "deg", "좌표", "EPSG:4326", "Y", ""],
    ["MD-LON", "경도", "Longitude", "LON", "경도좌표|lonDgr",
     "deg", "좌표", "EPSG:4326", "Y", ""],
    ["MD-ORG", "조사기관명", "Organization Name", "ORG_NM", "기관명|조사기관|검사기관",
     "", "기관", "공공데이터 공통표준용어", "Y", ""],
]
METADATA_COLUMNS = ["code", "name_ko", "name_en", "abbr", "synonyms",
                    "unit", "category", "reference", "verified", "note"]


def write_fixture_ontology(ontology_dir: Path) -> None:
    ontology_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(MEASUREMENT_ROWS, columns=MEASUREMENT_COLUMNS).to_csv(
        ontology_dir / "measurement_terms.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(METADATA_ROWS, columns=METADATA_COLUMNS).to_csv(
        ontology_dir / "metadata_terms.csv", index=False, encoding="utf-8-sig")


def write_sample_files(samples_dir: Path) -> list[Path]:
    """요구된 테스트 케이스를 담은 테스트 엑셀 3개 생성."""
    samples_dir.mkdir(parents=True, exist_ok=True)

    # 1) 정확 일치 케이스: 총질소, itemBod (+ 메타 컬럼, pH)
    f1 = samples_dir / "test1_exact.xlsx"
    pd.DataFrame(
        [["가평-1", "2026-07-01 10:00", 2.31, 1.8, 7.2],
         ["가평-2", "2026-07-01 11:00", 1.95, 2.1, 7.4]],
        columns=["측정소명", "측정일시", "총질소", "itemBod", "pH"],
    ).to_excel(f1, index=False)

    # 2) 변형/무관 케이스: 오타(총소질소), 단위 붙은 변형(BOD 괄호 약어), WATT·FACLT_NM(무관)
    f2 = samples_dir / "test2_variants.xlsx"
    pd.DataFrame(
        [["춘천-1", 2.02, 1.5, 340, "의암댐관리소"],
         ["춘천-2", 2.44, 1.7, 355, "의암댐관리소"]],
        columns=["측정소명", "총소질소", "생물학적 산소요구량(BOD_L당mg)", "WATT", "FACLT_NM"],
    ).to_excel(f2, index=False)

    # 3) 헤더가 2행(index 1)에 있는 파일: 정확 일치 T-N 포함
    f3 = samples_dir / "test3_header_row2.xlsx"
    header = ["측정소코드", "T-N", "총인", "수온(℃)"]
    rows = [
        ["2026년 상반기 수질측정 결과보고", None, None, None],  # 1행: 제목
        header,                                                  # 2행: 실제 헤더
        ["S001", 2.11, 0.045, 18.2],
        ["S002", 1.87, 0.051, 19.0],
    ]
    pd.DataFrame(rows).to_excel(f3, index=False, header=False)

    return [f1, f2, f3]
