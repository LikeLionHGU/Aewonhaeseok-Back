#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
수질 데이터 표준 용어 사전 — 시드 빌더

이 스크립트는 '부트스트랩'용이다. 한 번 돌려 CSV/SQL/XLSX를 만들고 PostgreSQL에
적재한 뒤부터는 DB가 원본이고 이 파일은 이력으로만 남는다. 새 동의어는 스크립트를
고치는 게 아니라 term_synonyms에 INSERT 하거나 unresolved_columns를 승격해서 넣는다.

출력:
  measurement_terms.csv  metadata_terms.csv  term_sources.csv  term_synonyms.csv
  seed.sql
  수질_표준사전_v1.xlsx

실행:  python3 build_dictionary.py
"""

import csv
import os
from datetime import date

OUT = os.path.dirname(os.path.abspath(__file__))

# 이 사전의 근거를 수집·검증한 날. 동의어의 collected_on 기본값.
COLLECTED = "2026-08-05"

LAW13 = "물환경보전법 시행규칙 별표 13"
LAW13_URL = "https://www.law.go.kr/법령/물환경보전법시행규칙"
LAW13_REV = "개정 2025. 3. 20."
# 별표 13 나목 9) — 현행 항목표가 적용되는 시행일
EFF_2021 = "2021-01-01"
# 별표 13 가목 2) — BOD/TOC/SS 기준이 적용되는 시행일
EFF_2020 = "2020-01-01"

# ---------------------------------------------------------------------------
# 1. 출처 레지스트리
#    reliability: legal > standard > spec > observed > inferred
#    observed = 실제 API 응답이나 내려받은 파일의 헤더에서 두 눈으로 확인한 것
# ---------------------------------------------------------------------------
SOURCES = [
    # (source_id, source_name, organization, source_type, base_url, access_note, encoding, reliability)
    ("LAW_ANNEX13", "물환경보전법 시행규칙 별표 13 수질오염물질의 배출허용기준",
     "환경부", "legal", LAW13_URL,
     "PDF 원문 19쪽 전문 대조 (개정 2025.3.20)", "UTF-8", "legal"),

    ("LAW_ANNEX3", "물환경보전법 시행규칙 별표 3 특정수질유해물질(제4조 관련)",
     "환경부", "legal",
     "https://www.law.go.kr/lsBylInfoPLinkR.do?bylCls=BE&lsNm=%EB%AC%BC%ED%99%98%EA%B2%BD%EB%B3%B4%EC%A0%84%EB%B2%95+%EC%8B%9C%ED%96%89%EA%B7%9C%EC%B9%99&bylNo=0003&bylBrNo=00",
     "개정 2017.1.19. 33개 호 중 제11호 삭제 → 실제 32종. "
     "특정수질유해물질 '목록'의 정본은 별표 3이며 별표 13의2는 폐수배출시설 적용기준(제35조의2)임",
     "UTF-8", "legal"),

    ("LAW_ENV_STD", "환경정책기본법 시행령 별표 1 환경기준(제2조 관련)",
     "환경부", "legal", "https://www.law.go.kr/LSW/flDownload.do?flSeq=159452669",
     "개정 2025.10.1. 하천/호소 생활환경기준 + 사람의 건강보호 기준. "
     "별표 13과 같은 물질을 다르게 표기하는 사례 다수", "UTF-8", "legal"),

    ("LAW_DRINKING", "먹는물 수질기준 및 검사 등에 관한 규칙 별표 1 먹는물의 수질기준(제2조 관련)",
     "환경부", "legal", "https://www.law.go.kr/LSW/flDownload.do?flSeq=158952499",
     "개정 2021.9.16. 먹는물·수돗물 수질기준의 정본. "
     "「먹는물관리법 시행규칙」 별표 1은 '환경영향조사의 조사항목'이지 수질기준이 아니다. "
     "먹는물관리법 제5조3항과 수도법 제26조2항이 모두 이 규칙 제2조로 위임된다",
     "UTF-8", "legal"),

    ("LAW_WATERWORKS", "수도법 시행규칙 (제22조의2 위생상의 조치 / 제22조의4 저수조 점검)",
     "환경부", "legal", "https://www.law.go.kr/법령/수도법시행규칙",
     "잔류염소의 하한 기준이 여기 있다. 상한(4.0㎎/L)은 먹는물검사규칙 별표 1 제4호 가목 — "
     "흔히 말하는 '수돗물 잔류염소 0.1~4.0'은 두 규칙의 합성이다",
     "UTF-8", "legal"),

    ("MOIS_STD_TERM", "행정안전부 공공데이터 공통표준용어(20251101, 8차)",
     "행정안전부", "standard", "https://www.data.go.kr/data/15156379/fileData.do",
     "CSV 13,176건 전수 조회. 제정 고시 제2020-42호(2020.8.6.), 개정 제2020-66호(2020.12.10.). "
     "'수질' 포함 용어는 0건이나 수소이온농도·부유물질량·전기전도도는 개별 등재됨",
     "UTF-8", "standard"),

    ("NIER_WQ_API", "국립환경과학원 수질 DB Open API — 물환경 수질측정망 운영결과",
     "기후에너지환경부 국립환경과학원", "spec",
     "https://www.data.go.kr/data/15081073/openapi.do",
     "getWaterMeasuringList. 실호출은 ServiceKey 필요, 출력결과 명세표로 확인(77필드)",
     "UTF-8", "spec"),

    ("SEOUL_WPOS", "서울 열린데이터광장 — 한강 및 주요지천 수질 측정 자료(OA-15488)",
     "서울특별시", "api",
     "http://openapi.seoul.go.kr:8088/sample/json/WPOSInformationTime/1/5/",
     "인증키에 sample 입력 시 5건 무료 호출. 실제 응답 JSON에서 필드명 확인",
     "UTF-8", "observed"),

    ("GG_WATER_API", "경기데이터드림 — 수도 정보 수질 현황(Wtrpipeinfowtrqultstus)",
     "경기도 / 제공: 한국수자원공사", "api",
     "https://data.gg.go.kr/portal/data/openapi/selectOpenApiMeta.do?infId=A8F378W1HRG03Q4GJHT423038583&infSeq=2",
     "정수장 수질. 메타 JSON은 비로그인 조회 가능, 실호출은 인증키 필요",
     "UTF-8", "spec"),

    ("GG_SPRING_API", "경기데이터드림 — 약수터 수질측정 결과 현황",
     "경기도", "api",
     "https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId=3PS7152M60Q0ZAG0427012039966&infSeq=3",
     "출력필드 19개를 상세페이지 명세에서 확인", "UTF-8", "spec"),

    ("DATAGO_JB", "전북특별자치도 보건환경연구원 하천수질측정망",
     "전북특별자치도", "file", "https://www.data.go.kr/data/3038768/fileData.do",
     "CSV 직접 다운로드 12,846행(2010.01~2023.12). 헤더 실측", "CP949", "observed"),

    ("DATAGO_JEJU", "제주특별자치도 하천수질조사결과",
     "제주특별자치도", "file", "https://www.data.go.kr/data/15064129/fileData.do",
     "CSV 헤더 실측", "CP949", "observed"),

    ("DATAGO_ANYANG", "경기도 안양시 안양천 수질측정 정보",
     "경기도 안양시", "file", "https://www.data.go.kr/data/3079518/fileData.do",
     "CSV 헤더 실측. 원문에 '총소질소' 오타 존재", "CP949", "observed"),

    ("DATAGO_GIMHAE", "경상남도 김해시 하천수질 현황",
     "경상남도 김해시", "file", "https://www.data.go.kr/data/15092533/fileData.do",
     "CSV 헤더 실측. 단위를 컬럼명 안에 표기하는 사례", "CP949", "observed"),

    ("DATAGO_INCHEON", "인천광역시 수질오염",
     "인천광역시", "file", "https://www.data.go.kr/data/15066383/fileData.do",
     "CSV 헤더 실측. 하천명이 컬럼명에 병합된 wide 피벗 구조", "CP949", "observed"),

    ("DATAGO_DANGJIN", "충청남도 당진시 상수도 수질검사",
     "충청남도 당진시", "file", "https://www.data.go.kr/",
     "CSV 헤더 실측(60항목). UTF-8 BOM", "UTF-8 BOM", "observed"),

    ("DATAGO_BUSAN", "부산광역시 약수터 수질검사",
     "부산광역시", "file", "https://www.data.go.kr/",
     "CSV 헤더 실측", "CP949", "observed"),

    ("DRAFT_AI", "팀 내부 초안 (수질_측정항목_표준사전_초안.xlsx)",
     "팀 자체 작성", "manual", None,
     "AI가 생성한 미검증 표기. 법령·실데이터로 확인되기 전에는 근거로 인용 금지",
     "UTF-8", "inferred"),

    ("MANUAL", "사람이 직접 입력",
     "팀 자체 작성", "manual", None, "운영 중 수기 추가분", "UTF-8", "inferred"),
]

# ---------------------------------------------------------------------------
# 2. measurement_terms — 측정항목
#    std_name은 반드시 법령 원문 표기 그대로. 읽기 좋은 표기는 동의어로 넣는다.
#    (code, std_name, name_en, abbr, unit, category, legal_basis,
#     effective_from, legal_status, is_toxic, review_status, note)
# ---------------------------------------------------------------------------
M = []


# 특정수질유해물질 — 물환경보전법 시행규칙 [별표 3](제4조 관련), 개정 2017.1.19.
# 33개 호 중 제11호는 "삭제 <2016. 5. 20.>"이므로 실제 물질은 32종.
# 초안은 이 근거를 '별표 13의2'로 적었으나, 별표 13의2는 폐수배출시설 적용기준이고
# 목록의 정본은 별표 3이다. {표준코드: (호수, 별표 3 원문 표기)}
TOXIC = {
    "WQ-023": (1, "구리와 그 화합물"),
    "WQ-021": (2, "납과 그 화합물"),
    "WQ-022": (3, "비소와 그 화합물"),
    "WQ-020": (4, "수은과 그 화합물"),
    "WQ-016": (5, "시안화합물"),
    "WQ-028": (6, "유기인 화합물"),
    "WQ-018": (7, "6가크롬 화합물"),
    "WQ-019": (8, "카드뮴과 그 화합물"),
    "WQ-033": (9, "테트라클로로에틸렌"),
    "WQ-032": (10, "트리클로로에틸렌"),
    # 제11호 삭제 <2016. 5. 20.>
    "WQ-029": (12, "폴리클로리네이티드바이페닐"),
    "WQ-045": (13, "셀레늄과 그 화합물"),
    "WQ-034": (14, "벤젠"),
    "WQ-048": (15, "사염화탄소"),
    "WQ-035": (16, "디클로로메탄"),
    "WQ-036": (17, "1, 1-디클로로에틸렌"),
    "WQ-049": (18, "1, 2-디클로로에탄"),
    "WQ-037": (19, "클로로포름"),
    "WQ-038": (20, "1,4-다이옥산"),
    "WQ-051": (21, "디에틸헥실프탈레이트(DEHP)"),
    "WQ-052": (22, "염화비닐"),
    "WQ-040": (23, "아크릴로니트릴"),
    "WQ-053": (24, "브로모포름"),
    "WQ-043": (25, "아크릴아미드"),
    "WQ-041": (26, "나프탈렌"),
    "WQ-039": (27, "폼알데하이드"),
    "WQ-054": (28, "에피클로로하이드린"),
    "WQ-030": (29, "페놀"),
    "WQ-031": (30, "펜타클로로페놀"),
    "WQ-044": (31, "스티렌"),
    "WQ-058": (32, "비스(2-에틸헥실)아디페이트"),
    "WQ-059": (33, "안티몬"),
}


def m(code, std, en, abbr, unit, cat, basis, eff, status, toxic, review, note=""):
    # 특정수질유해물질 여부는 추정하지 않고 별표 3 목록으로만 판정한다.
    if code in TOXIC:
        toxic = True
        tbasis = "물환경보전법 시행규칙 별표 3 제%d호(%s)" % TOXIC[code]
    else:
        toxic = False if toxic is not False and status == "statutory" else toxic
        tbasis = "별표 3 목록에 없음" if status == "statutory" else ""
    M.append(dict(code=code, std_name=std, name_en=en, abbr=abbr, unit=unit,
                  category=cat, legal_basis=basis, legal_article="제34조",
                  legal_effective_from=eff, legal_revision=LAW13_REV,
                  legal_status=status, is_toxic_substance=toxic,
                  toxic_substance_basis=tbasis,
                  source_url=LAW13_URL if basis == LAW13 else "",
                  review_status=review, reviewed_by="", reviewed_at="", note=note))


# --- 별표 13 가목: 유기물·부유물질 ------------------------------------------
m("WQ-001", "생물화학적산소요구량", "Biochemical Oxygen Demand", "BOD", "㎎/L",
  "유기물", LAW13, EFF_2020, "statutory", False, "verified",
  "별표 13 가목 2) 표. 같은 표 안에서 '생물화학적 산소요구량'(띄어쓰기)으로도 표기됨 — 동의어로 등록")
m("WQ-002", "총유기탄소량", "Total Organic Carbon", "TOC", "㎎/L",
  "유기물", LAW13, EFF_2020, "statutory", False, "verified",
  "2020.1.1부터 COD를 대체한 현행 유기물 지표")
m("WQ-003", "화학적산소요구량", "Chemical Oxygen Demand", "COD", "㎎/L",
  "유기물", LAW13, "2008-01-01", "superseded", False, "verified",
  "별표 13 가목 1), 2019.12.31까지 적용. 과거 데이터 호환용 — 현행 기준으로 쓰면 안 됨")
m("WQ-004", "부유물질량", "Suspended Solids", "SS", "㎎/L",
  "일반", LAW13, EFF_2020, "statutory", False, "verified", "")

# --- 별표 13 나목 9) 현행 (2021.1.1~), 법령 표기 순서 -----------------------
m("WQ-008", "수소이온농도", "Hydrogen Ion Concentration", "pH", "-",
  "일반", LAW13, EFF_2021, "statutory", False, "verified",
  "법령은 단위 없이 범위(5.8~8.6)로 규정")
m("WQ-012", "노말헥산추출물질함유량 광유류", "n-Hexane Extractable Material, Mineral Oil",
  "n-H광유", "㎎/L", "유류", LAW13, EFF_2021, "statutory", False, "verified",
  "'노말헥산추출물질함유량' 아래 광유류/동식물유지류 2개 행으로 규정 — 별개 항목으로 분리해야 함")
m("WQ-013", "노말헥산추출물질함유량 동식물유지류",
  "n-Hexane Extractable Material, Animal and Vegetable Fats and Oils",
  "n-H동식물", "㎎/L", "유류", LAW13, EFF_2021, "statutory", False, "verified", "")
m("WQ-015", "페놀류함유량", "Phenols", "-", "㎎/L",
  "유해물질", LAW13, EFF_2021, "statutory", None, "verified",
  "단일물질 '페놀'(WQ-030)과 별개 항목. 법령에 두 행이 따로 있음")
m("WQ-030", "페놀", "Phenol", "-", "㎎/L",
  "유해물질", LAW13, "2017-01-01", "statutory", None, "verified",
  "2017.1.1 기준부터 별도 항목으로 신설")
m("WQ-031", "펜타클로로페놀", "Pentachlorophenol", "PCP", "㎎/L",
  "유해물질", LAW13, "2017-01-01", "statutory", None, "verified", "")
m("WQ-016", "시안함유량", "Cyanide", "CN", "㎎/L",
  "유해물질", LAW13, EFF_2021, "statutory", None, "verified", "")
m("WQ-017", "크롬함유량", "Chromium", "Cr", "㎎/L",
  "중금속", LAW13, EFF_2021, "statutory", None, "verified", "총크롬. 6가크롬(WQ-018)과 별개")
m("WQ-025", "용해성철함유량", "Dissolved Iron", "Fe", "㎎/L",
  "중금속", LAW13, EFF_2021, "statutory", None, "verified", "")
m("WQ-024", "아연함유량", "Zinc", "Zn", "㎎/L",
  "중금속", LAW13, EFF_2021, "statutory", None, "verified", "")
m("WQ-023", "구리(동)함유량", "Copper", "Cu", "㎎/L",
  "중금속", LAW13, EFF_2021, "statutory", None, "verified",
  "법령 표기에 한자어 '동'이 괄호로 병기됨")
m("WQ-019", "카드뮴함유량", "Cadmium", "Cd", "㎎/L",
  "중금속", LAW13, EFF_2021, "statutory", None, "verified", "")
m("WQ-020", "수은함유량", "Mercury", "Hg", "㎎/L",
  "중금속", LAW13, EFF_2021, "statutory", None, "verified", "")
m("WQ-028", "유기인함유량", "Organophosphorus Compounds", "OP", "㎎/L",
  "유해물질", LAW13, EFF_2021, "statutory", None, "verified", "")
m("WQ-022", "비소함유량", "Arsenic", "As", "㎎/L",
  "중금속", LAW13, EFF_2021, "statutory", None, "verified", "")
m("WQ-021", "납함유량", "Lead", "Pb", "㎎/L",
  "중금속", LAW13, EFF_2021, "statutory", None, "verified", "")
m("WQ-018", "6가크롬함유량", "Hexavalent Chromium", "Cr6+", "㎎/L",
  "중금속", LAW13, EFF_2021, "statutory", None, "verified", "")
m("WQ-026", "용해성망간함유량", "Dissolved Manganese", "Mn", "㎎/L",
  "중금속", LAW13, EFF_2021, "statutory", None, "verified", "")
m("WQ-027", "플로오르(불소)함유량", "Fluorine (Fluoride)", "F", "㎎/L",
  "유해물질", LAW13, EFF_2021, "statutory", None, "verified",
  "법령 원문 표기가 '플로오르(불소)'. 초안의 '플루오린'은 법령 표기가 아니므로 동의어로 강등")
m("WQ-029", "PCB함유량", "Polychlorinated Biphenyls", "PCB", "㎎/L",
  "유해물질", LAW13, EFF_2021, "statutory", None, "verified",
  "2019~2020 기준표에서는 '폴리클로리네이티드바이페닐(PCB)함유량'으로 표기 — 동의어 등록")
m("WQ-011", "총대장균군", "Total Coliforms", "TC", "군수/㎖",
  "미생물", LAW13, EFF_2021, "statutory", False, "verified",
  "법령 표기: 총대장균군(群)(총대장균군수)(㎖)")
m("WQ-010", "색도", "Color", "-", "도",
  "일반", LAW13, EFF_2021, "statutory", False, "verified",
  "섬유염색·펄프 등 일부 시설에만 적용되는 기준")
m("WQ-009", "온도", "Temperature", "-", "℃",
  "일반", LAW13, EFF_2021, "statutory", False, "verified",
  "법령 표기는 '온도'. 실데이터는 대부분 '수온'으로 쓴다")
m("WQ-005", "총질소", "Total Nitrogen", "T-N", "㎎/L",
  "영양염류", LAW13, EFF_2021, "statutory", False, "verified", "")
m("WQ-006", "총인", "Total Phosphorus", "T-P", "㎎/L",
  "영양염류", LAW13, EFF_2021, "statutory", False, "verified", "")
m("WQ-032", "트리클로로에틸렌", "Trichloroethylene", "TCE", "㎎/L",
  "휘발성유기화합물", LAW13, EFF_2021, "statutory", None, "verified", "")
m("WQ-033", "테트라클로로에틸렌", "Tetrachloroethylene", "PCE", "㎎/L",
  "휘발성유기화합물", LAW13, EFF_2021, "statutory", None, "verified", "")
m("WQ-014", "음이온계면활성제", "Anionic Surfactants", "ABS", "㎎/L",
  "일반", LAW13, EFF_2021, "statutory", False, "verified", "")
m("WQ-034", "벤젠", "Benzene", "-", "㎎/L",
  "휘발성유기화합물", LAW13, EFF_2021, "statutory", None, "verified", "")
m("WQ-035", "디클로로메탄", "Dichloromethane", "DCM", "㎎/L",
  "휘발성유기화합물", LAW13, EFF_2021, "statutory", None, "verified", "")
m("WQ-007", "생태독성", "Ecological Toxicity", "TU", "TU",
  "생태독성", LAW13, EFF_2021, "statutory", False, "verified",
  "법령 표기: 생태독성(TU). 물벼룩 급성독성시험 기준")
m("WQ-045", "셀레늄함유량", "Selenium", "Se", "㎎/L",
  "중금속", LAW13, EFF_2021, "statutory", None, "verified", "")
m("WQ-048", "사염화탄소", "Carbon Tetrachloride", "-", "㎎/L",
  "휘발성유기화합물", LAW13, EFF_2021, "statutory", None, "verified", "초안 누락분")
m("WQ-036", "1,1-디클로로에틸렌", "1,1-Dichloroethylene", "1,1-DCE", "㎎/L",
  "휘발성유기화합물", LAW13, EFF_2021, "statutory", None, "verified", "")
m("WQ-049", "1,2-디클로로에탄", "1,2-Dichloroethane", "1,2-DCE", "㎎/L",
  "휘발성유기화합물", LAW13, EFF_2021, "statutory", None, "verified", "초안 누락분")
m("WQ-037", "클로로포름", "Chloroform", "-", "㎎/L",
  "휘발성유기화합물", LAW13, EFF_2021, "statutory", None, "verified", "")
m("WQ-050", "니켈", "Nickel", "Ni", "㎎/L",
  "중금속", LAW13, EFF_2021, "statutory", None, "verified", "초안 누락분")
m("WQ-046", "바륨", "Barium", "Ba", "㎎/L",
  "중금속", LAW13, EFF_2021, "statutory", None, "verified", "")
m("WQ-038", "1,4-다이옥산", "1,4-Dioxane", "-", "㎎/L",
  "유해물질", LAW13, EFF_2021, "statutory", None, "verified",
  "법령 원문은 '1,4-다이옥산'. 초안의 '1,4-다이옥세인'은 법령 표기가 아님 — 동의어로 강등")
m("WQ-051", "디에틸헥실프탈레이트(DEHP)", "Di-2-ethylhexyl Phthalate", "DEHP", "㎎/L",
  "유해물질", LAW13, EFF_2021, "statutory", None, "verified", "초안 누락분")
m("WQ-052", "염화비닐", "Vinyl Chloride", "VC", "㎎/L",
  "휘발성유기화합물", LAW13, EFF_2021, "statutory", None, "verified", "초안 누락분")
m("WQ-040", "아크릴로니트릴", "Acrylonitrile", "AN", "㎎/L",
  "유해물질", LAW13, EFF_2021, "statutory", None, "verified", "")
m("WQ-053", "브로모포름", "Bromoform", "-", "㎎/L",
  "휘발성유기화합물", LAW13, EFF_2021, "statutory", None, "verified", "초안 누락분")
m("WQ-041", "나프탈렌", "Naphthalene", "-", "㎎/L",
  "유해물질", LAW13, "2016-01-01", "statutory", None, "verified", "")
m("WQ-039", "폼알데하이드", "Formaldehyde", "HCHO", "㎎/L",
  "유해물질", LAW13, "2016-01-01", "statutory", None, "verified",
  "법령 원문은 '폼알데하이드'. 초안의 '포름알데히드'는 법령 표기가 아님 — 동의어로 강등")
m("WQ-054", "에피클로로하이드린", "Epichlorohydrin", "-", "㎎/L",
  "유해물질", LAW13, "2016-01-01", "statutory", None, "verified", "초안 누락분")
m("WQ-055", "톨루엔", "Toluene", "-", "㎎/L",
  "휘발성유기화합물", LAW13, "2016-01-01", "statutory", None, "verified", "초안 누락분")
m("WQ-056", "자일렌", "Xylene", "-", "㎎/L",
  "휘발성유기화합물", LAW13, "2016-01-01", "statutory", None, "verified", "초안 누락분")
m("WQ-057", "퍼클로레이트", "Perchlorate", "-", "㎎/L",
  "유해물질", LAW13, "2019-01-01", "statutory", None, "verified",
  "초안 누락분. 기초무기화학물질·비철금속 제련 시설은 별도 기준 적용")
m("WQ-043", "아크릴아미드", "Acrylamide", "-", "㎎/L",
  "유해물질", LAW13, "2019-01-01", "statutory", None, "verified", "")
m("WQ-044", "스티렌", "Styrene", "-", "㎎/L",
  "휘발성유기화합물", LAW13, "2019-01-01", "statutory", None, "verified", "")
m("WQ-058", "비스(2-에틸헥실)아디페이트", "Bis-2-ethylhexyl Adipate", "DEHA", "㎎/L",
  "유해물질", LAW13, "2019-01-01", "statutory", None, "verified", "초안 누락분")
m("WQ-059", "안티몬", "Antimony", "Sb", "㎎/L",
  "중금속", LAW13, "2019-01-01", "statutory", None, "verified", "초안 누락분")
m("WQ-047", "주석", "Tin", "Sn", "㎎/L",
  "중금속", LAW13, EFF_2021, "statutory", None, "verified", "")

# --- 초안에 있었으나 별표 13에서 확인되지 않은 항목 ---------------------------
m("WQ-042", "폼산", "Formic Acid", "-", "㎎/L",
  "유해물질", "", "", "non_statutory", None, "rejected",
  "초안(AI 생성)에 있었으나 별표 13 전체(19쪽) 어디에도 없음. 근거 확인 전까지 사용 금지. "
  "코드는 재사용 방지를 위해 남겨 둔다")

# --- 법정 배출기준 외 관측항목: 하천·상수도 데이터에 실재 --------------------
# 배출허용기준(별표 13)에는 없지만 다른 법령·기준에 근거가 있는 항목들.
ENV_STD = "환경정책기본법 시행령 별표 1 환경기준(제2조 관련)"
m("WQ-060", "용존산소량", "Dissolved Oxygen", "DO", "㎎/L",
  "일반", ENV_STD + " — 하천 생활환경 기준", "", "non_statutory",
  False, "verified",
  "배출허용기준 항목은 아니지만 하천 환경기준의 정식 항목이자 하천 데이터의 핵심 컬럼")
m("WQ-061", "클로로필-a", "Chlorophyll-a", "Chl-a", "㎎/㎥",
  "일반", ENV_STD + " — 호소 생활환경 기준", "", "non_statutory",
  False, "verified",
  "하천 기준에는 없고 '호소' 기준에만 있는 항목. 법령 단위는 ㎎/㎥이나 데이터는 ㎎/L로 오는 "
  "경우가 있어 값 해석 시 1000배 차이 주의")
m("WQ-062", "전기전도도", "Electrical Conductivity", "EC", "μS/㎝",
  "일반", "공공데이터 공통표준용어(ELCD)", "", "non_statutory", False, "draft",
  "환경정책기본법 시행령 별표 1 전문 검색 결과 0건 — 환경기준 항목이 아님. "
  "공통표준용어에는 '전기전도도 ELCD'로 등재. 측정 근거는 수질오염공정시험기준에서 재확인 필요")
m("WQ-063", "분원성대장균군", "Fecal Coliforms", "FC", "군수/100mL",
  "미생물", ENV_STD + " — 하천 생활환경 기준", "", "non_statutory",
  False, "verified",
  "환경기준 단위는 군수/100mL. 별표 13의 총대장균군은 군수/㎖ — 단위 기준이 서로 다르다")
DRINK = "먹는물 수질기준 및 검사 등에 관한 규칙 별표 1(제2조 관련)"
m("WQ-064", "암모니아성 질소", "Ammonia Nitrogen", "NH3-N", "㎎/L",
  "영양염류", DRINK + " 제2호 아목", "", "non_statutory", False, "verified",
  "기준 0.5㎎/L. 법령 표기에 공백이 있다('암모니아성 질소')")
m("WQ-065", "질산성 질소", "Nitrate Nitrogen", "NO3-N", "㎎/L",
  "영양염류", DRINK + " 제2호 자목", "", "non_statutory", False, "verified",
  "기준 10㎎/L. 법령 표기에 공백이 있다('질산성 질소')")
m("WQ-066", "인산염 인", "Phosphate Phosphorus", "PO4-P", "㎎/L",
  "영양염류", "수질오염공정시험기준", "", "non_statutory", False, "draft", "")
m("WQ-067", "용존총질소", "Dissolved Total Nitrogen", "DTN", "㎎/L",
  "영양염류", "수질오염공정시험기준", "", "non_statutory", False, "draft", "")
m("WQ-068", "용존총인", "Dissolved Total Phosphorus", "DTP", "㎎/L",
  "영양염류", "수질오염공정시험기준", "", "non_statutory", False, "draft", "")
m("WQ-069", "탁도", "Turbidity", "NTU", "NTU",
  "일반", DRINK + " 제5호 파목", "", "non_statutory", False, "verified",
  "기준 1NTU, 수돗물은 0.5NTU. 정수장은 수도법 시행규칙 별표 5의3이 별도 기준(0.3NTU)을 둔다")
m("WQ-070", "잔류염소(유리잔류염소를 말한다)", "Residual Chlorine (Free)", "-", "㎎/L",
  "일반", DRINK + " 제4호 가목", "", "non_statutory", False, "verified",
  "괄호 정의문까지가 법령상 항목명이다. 상한 4.0㎎/L는 이 규칙, 하한 0.1㎎/L는 수도법 시행규칙 "
  "제22조의2제1항제3호 — '수돗물 0.1~4.0'은 단일 조문이 아니라 두 규칙의 합성이다")
m("WQ-071", "일반세균", "Heterotrophic Plate Count", "-", "CFU/mL",
  "미생물", DRINK + " 제1호 가목", "", "non_statutory", False, "verified",
  "기준 100CFU/mL. 샘물·염지하수는 저온일반세균/중온일반세균으로 나뉜다")
m("WQ-072", "과망간산칼륨 소비량", "Potassium Permanganate Consumption", "-", "㎎/L",
  "유기물", DRINK + " 제5호 나목", "", "non_statutory", False, "verified",
  "기준 10㎎/L. 법령 표기에 공백이 있다('과망간산칼륨 소비량')")
m("WQ-073", "투명도", "Transparency", "-", "m",
  "일반", "수질오염공정시험기준", "", "non_statutory", False, "draft",
  "국립환경과학원 API 명세는 단위를 ㎎/L로 적어 두었으나 실제로는 길이 단위 — 명세 오류로 보임")
m("WQ-074", "수위", "Water Level", "-", "m",
  "수문", "", "", "non_statutory", False, "draft", "수질 항목이 아니라 수문 관측값")
m("WQ-075", "유량", "Flow Rate", "-", "㎥/s",
  "수문", "", "", "non_statutory", False, "draft", "")
m("WQ-076", "헥사클로로벤젠", "Hexachlorobenzene", "HCB", "㎎/L",
  "유해물질", ENV_STD + " — 하천 사람의 건강보호 기준", "", "non_statutory", False, "verified",
  "별표 13 배출허용기준에는 없고 환경기준(사람의 건강보호)에 있는 항목. "
  "국립환경과학원 API의 itemHcb가 여기에 대응한다")

# ---------------------------------------------------------------------------
# 3. metadata_terms — 관측 메타
#    (code, std_name, name_en, abbr, std_domain, value_type, facet,
#     canonical_format, normalization_note, note)
# ---------------------------------------------------------------------------
D = []


MOIS = "공공데이터 공통표준용어(행정안전부, 20251101 8차)"
MOIS_URL = "https://www.data.go.kr/data/15156379/fileData.do"
UNCHECKED = "미확인 — 공통표준용어 13,176건 대조 필요"


def d(code, std, en, abbr, domain, vtype, facet, fmt="", norm="", note="",
      basis=MOIS, review="verified"):
    """basis 기본값은 공통표준용어 등재 확인분. 미확인 항목은 basis=UNCHECKED로 넘긴다."""
    D.append(dict(code=code, std_name=std, name_en=en, abbr=abbr,
                  std_domain=domain, value_type=vtype, facet=facet,
                  standard_basis=basis,
                  source_url=MOIS_URL if basis == MOIS else "",
                  canonical_format=fmt, normalization_note=norm,
                  review_status=review, reviewed_by="", reviewed_at="", note=note))


# --- 지점 -------------------------------------------------------------------
d("MD-001", "측정소명", "Station Name", "MSRSTN_NM", "명V200", "text", "station", "",
  "소스마다 측정소명/조사지점명/시설명/하천명으로 부른다. 지점 마스터와 대조해 코드로 승격 필요",
  "공통표준용어 등재(5차 2022-07). 서울시 API의 MSRSTN_NM은 이 표준을 그대로 따른 사례")
d("MD-002", "측정소코드", "Station Code", "MSRSTN_CD", "코드", "code", "station", "",
  "기관마다 코드 체계가 달라 그대로는 조인 불가",
  "공통표준용어 미등재(용어명·이음동의어 exact 0건, 8차 20251101). 꼬리 '코드'도 미등재라 "
  "차용 경로가 없어 조합으로 간다. 현행 공통표준단어 측정소 MSRSTN(測定所 '재는 장소', 5차) + "
  "코드 CD(형식단어, 도메인분류 코드) 조합. 동음이의 없음(측정소·코드 각 1건), 약어 충돌 0건. "
  "자릿수는 기관마다 달라 도메인분류명만 적고 구체 자릿수는 두지 않는다",
  basis="공통표준용어 미등재 — 공통표준단어 조합(기관표준용어)", review="verified")
d("MD-003", "하천명", "River Name", "RVR_NM", "명V100", "text", "station", "",
  "측정소명과 구분해야 한다. 하천명만 있고 지점이 없는 데이터가 존재",
  "공통표준용어 등재(5차 2022-07)")
d("MD-004", "시설명", "Facility Name", "FCLT_NM", "명V256", "text", "station", "",
  "정수장·물재생센터·약수터 등 시설 단위 관측의 지점명. 측정소명(MD-001)과 구분",
  "공통표준용어 등재 확인(8차 20251101, exact match). 영문약어 FCLT_NM, 도메인 명V256. "
  "실데이터 표기 FACLT_NM(경기 수도정보 API)이 이 표준약어와 대응하여 채택. "
  "이음동의어 '시설이름·시설명칭'도 등재됨. 구 표준명 '측정시설명'은 동의어로 보존")
d("MD-005", "시설번호", "Facility Number", "FCLT_NO", "번호V20", "code", "station", "", "",
  "공통표준용어 등재 확인(8차 20251101, exact match). 영문약어 FCLT_NO, 도메인 번호V20. "
  "실데이터 표기 FACLT_NO(경기 수도정보 API)가 이 표준약어와 대응하여 채택. "
  "구 표준명 '측정시설번호'는 동의어로 보존")
d("MD-030", "채수지점번호", "Sampling Spot Number", "-", "", "code",
  "station", "", "",
  "공통표준용어 미등재(exact 0건, 8차 20251101). 조합도 불가 — 공통표준단어 '지점' BRNCH는 "
  "支店(본점에서 갈라져 나온 점포)이라 측정 地點이 아니다(BRNCH_ 접두 현행 7건 전부 상업 점포). "
  "地點 계열은 '측정지점' MSPT·'관측지점' OBSPT로 따로 등재돼 있다. 근접 용어 '측정지점번호' "
  "MSPT_NO(번호V50)가 있으나 우리 이름의 꼬리가 아니어서 포함관계 차용이 성립하지 않고, "
  "채수 장소와 측정 장소가 같은 실체인지도 원본 정의서 없이는 확인되지 않는다",
  basis="공통표준용어 미등재(exact 0건, 8차 20251101) — 지점=支店이라 조합 불가, 개념 동일성 미확인",
  review="draft")

# --- 시간 -------------------------------------------------------------------
d("MD-006", "측정일자", "Measurement Date", "MSRMT_YMD", "연월일C8", "date", "time",
  "YYYY-MM-DD",
  "실데이터 포맷이 2012.02.03 / 20260805 / 2021-04-11로 제각각 — 적재 시 통일",
  "공통표준용어 등재(3차 2021-10). 저장 YYYYMMDD / 표현 YYYY-MM-DD")
d("MD-007", "측정일시", "Measurement Datetime", "MSRMT_DT", "연월일시분초D", "timestamp",
  "time", "YYYY-MM-DD HH24:MI:SS",
  "날짜와 시각이 분리된 소스는 결합해서 채운다",
  "공통표준용어 등재(4차 2021-12)")
d("MD-008", "측정연도", "Measurement Year", "MSRMT_YR", "연도C4", "integer", "time", "YYYY",
  "연/월을 분리 저장하는 소스가 많다. 측정일자로 통합 가능하면 통합",
  "공통표준용어 등재 확인(8차 20251101, exact match). 설명: 일정한 양을 기준으로 하여 같은 종류의 다른 양의 크기를 잰 연도")
d("MD-009", "측정월", "Measurement Month", "MSRMT_MM", "월C2", "integer", "time", "MM",
  "'02'처럼 zero-pad 문자열로 오는 소스 있음",
  "공통표준용어 등재 확인(8차 20251101, exact match). 설명: 기계나 장치를 사용하여 일정한 양을 기준으로 같은 종류의 다른 양의 크기를 잰 월")
d("MD-010", "측정회차", "Measurement Round", "-", "", "text", "time", "",
  "값 미확보(NIER API ServiceKey 필요). 저장소에 값 스냅샷이 없다",
  "공통표준용어 미등재(용어명·이음동의어 exact 0건, 8차 20251101). '회차'는 공통표준단어 "
  "단독 등재 0건이라 조합도 불가. 근접 후보 '측정차수' MSRMT_CYCL과 '측정횟수' MSRMT_NMTM이 "
  "둘 다 수N10·7차(2024-11) 현행으로 병존해, 값이 서수(n번째 측정)인지 개수(총 몇 회)인지 "
  "모르면 확정할 수 없다. 표준은 회차→차수 매핑을 제공하지 않는다(이음동의어 0건)",
  basis="공통표준용어 미등재(exact 0건, 8차 20251101) — 서수/개수 미확인으로 후보 2택 미결",
  review="draft")
d("MD-011", "시료채취일자", "Sampling Date", "SPCM_PCKNG_YMD", "연월일C8", "date", "time",
  "YYYY-MM-DD",
  "측정일자(MD-006)와 개념이 다를 수 있다(채수일 vs 분석일) — 소스별 정의 확인 필요",
  "공통표준용어 등재(7차 2024-11). 별도로 '채수일자' WTSMP_YMD도 등재돼 있어 "
  "어느 쪽을 쓸지 팀 규칙이 필요하다")
d("MD-012", "측정시각", "Measurement Time", "MSRMT_TM", "시분초C6", "text", "time", "HH24:MI", "",
  "공통표준용어 등재 확인(8차 20251101, exact match). 설명: 기계나 장치를 사용하여 일정한 양을 기준으로 같은 종류의 다른 양의 크기를 재는 어느 한 시점")

# --- 공간 -------------------------------------------------------------------
d("MD-013", "위도", "Latitude", "LAT", "위도N12,10", "numeric", "space", "WGS84 십진도",
  "국립환경과학원은 도/분/초 3개 필드로 분리 제공(latDgr/latMin/latSec) — 십진도 환산 필요",
  "공통표준용어 등재(2차 2020-12), 소관 국토교통부. 표현형식 99.9999999999")
d("MD-014", "경도", "Longitude", "LOT", "경도N13,10", "numeric", "space", "WGS84 십진도",
  "동일하게 lonDgr/lonMin/lonSec 분리 제공",
  "공통표준용어 등재(2차 2020-12), 소관 국토교통부. 표준 약어가 LNG/LON이 아니라 LOT다")
d("MD-015", "소재지주소", "Address", "LCTN_ADDR", "주소V200", "text", "space", "", "",
  "공통표준용어 등재(4차 2021-12)")
d("MD-016", "도로명주소", "Road Name Address", "ROAD_NM_ADDR", "주소V200", "text", "space",
  "", "", "공통표준용어 등재(2차 2020-12), 소관 행정안전부. 상세 주소는 제외한다고 명시됨")
d("MD-017", "시도명", "Province Name", "CTPV_NM", "명V40", "text", "space", "",
  "'전라북도'처럼 개편 전 명칭이 데이터에 남아 있다(현 전북특별자치도)",
  "공통표준용어 등재(2차 2020-12). 단어 시도=CTPV(Cities And Provinces)")
d("MD-018", "시군구명", "District Name", "SGG_NM", "명V40", "text", "space", "", "",
  "공통표준용어 등재(2차 2020-12)")
d("MD-019", "법정동시군구코드", "Legal District Code", "STDG_SGG_CD", "코드C3", "code",
  "space", "3자리",
  "법정동코드 10자리 중 3~5번째 자리(110:종로구, 140:중구). 10자리 전체가 필요하면 "
  "'법정동코드' STDG_CD(코드C10)를 쓴다",
  "'시군구코드'는 공통표준용어에 없다(0건). 표준 명칭은 '법정동시군구코드'이므로 "
  "표준명을 그쪽으로 맞췄다. 소관 국토교통부")
d("MD-020", "읍면동명", "Town Name", "EMD_NM", "명", "text", "space", "",
  "전북 값 62종 중 '가' 표기 6종(다가동3가 등), 숫자형 행정동(평화1동 류) 0종. "
  "읍/면 9,695행 중 9,191행에 리가 채워지고 동·가 3,150행은 리 공란 — 다만 읍인데 리가 "
  "전무한 504행(운봉읍·삼례읍·신태인읍)이 있어 계층 근거로는 불충분",
  "공통표준용어 미등재(용어명·이음동의어 exact 0건, 8차 20251101). 꼬리 '명'·'동명'·'면동명' "
  "모두 미등재라 차용 경로가 없어 조합으로 간다. 현행 공통표준단어 읍면동 EMD(邑面洞 "
  "'행정 구역 단위인 읍·면·동을 아울러 이르는 말', 2차) + 명 NM(형식단어) 조합. "
  "동음이의 없음(읍면동 1건), 약어 충돌 0건. 표준 자신도 무수식 읍면동+명을 "
  "'영문읍면동명' ENG_EMD_NM(명V40, 현행)으로 쓴다. "
  "법정동/행정동 구분은 값의 의미 문제라 이름 판정을 막지 않는다 — norm 참조",
  basis="공통표준용어 미등재 — 공통표준단어 조합(기관표준용어)", review="verified")
d("MD-021", "리명", "Village Name", "LI_NM", "명", "text", "space", "",
  "전북 원본 컬럼명은 '동리 명'이고 비공백 고유값 53종이 전부 '리'로 끝난다",
  "공통표준용어 미등재(용어명·이음동의어 exact 0건, 8차 20251101. '행정리명'도 0건). "
  "꼬리 '명'·'리명' 모두 미등재라 차용 경로가 없어 조합으로 간다. 현행 공통표준단어 "
  "리 LI(里 '지방 행정의 말단 구역. 읍과 면의 아래에 둔다', 5차) + 명 NM(형식단어) 조합. "
  "동음이의 없음, 약어 충돌 0건. 종전 '법정리명' STLI_NM은 폐기, 현행은 '법정동리명' "
  "STDG_LI_NM(명V100)이나 이는 우리 이름보다 좁은 하위 개념이라 차용 대상이 아니다. "
  "MD-020과 동일 판정",
  basis="공통표준용어 미등재 — 공통표준단어 조합(기관표준용어)", review="verified")

# --- 기관 / 채취조건 / 품질 / 레코드 ----------------------------------------
d("MD-022", "기관명", "Institution Name", "INST_NM", "명V200", "text", "organization",
  "", "", "공통표준용어 등재(2차 2020-12). 코드가 필요하면 '기관코드' INST_CD(코드C7). "
  "초안의 '측정기관명'은 표준 명칭이 아니라 '기관명'이다")
d("MD-023", "용수구분명", "Water Use Type", "-", "", "text", "sampling", "", "",
  "공통표준용어 미등재(용어명·이음동의어 exact 0건, 8차 20251101). 포함관계 상위어 "
  "'구분명' SE_NM(명V100, 5차 2022-07)에서 개념을 차용. '용수'라는 수식어가 무엇의 구분인지를 "
  "담고 있어 '구분명'으로 개명하면 의미가 손실되므로 이름은 유지한다. "
  "abbr은 비운다 — 수식어가 붙은 표준용어는 기저 약어를 그대로 쓰지 않는다"
  "(수식어+등재용어 6,453쌍 전수 대조 결과 재사용 0건. 예: 용도구분명 USG_SE_NM). "
  "domain도 비운다 — 경기 API 실호출 응답값을 확보하지 못해 명V100 사양 충족을 확인할 수 없다"
  "('~구분명' 69건 중 명V100은 60건으로 계열 내에서도 확정적이지 않다)",
  basis="공통표준용어 '구분명' 차용", review="verified")
d("MD-024", "채수수심", "Sampling Depth", "-", "", "numeric", "sampling", "",
  "국립환경과학원 wmdep. 같은 지점 다른 수심의 값이 별도 행으로 오면 수심을 복합키에 포함해야 "
  "덮어쓰기가 나지 않는다. 단위 m는 명세에서 확인하지 못한 가정이라 뺐다. 값 미확보",
  "공통표준용어 미등재(exact 0건, 8차 20251101) — 말미 형식단어 미확정: '수심' WTDPT는 "
  "水深 '강이나 바다, 호수 따위의 물의 깊이'로 수체 자체의 깊이를 뜻하고(유일 용례 평균수심 "
  "AVG_WTDPT도 그렇다), 우리 개념은 시료를 뜬 위치의 깊이다. 표준의 행위어+깊이 관용은 "
  "'깊이' DPTH(굴착깊이 EXCV_DPTH 등)이고 採水 설명 자신이 '서로 다른 깊이의 물을 떠올리는 "
  "일'이라 쓴다. 채수 WTSMP는 확정이나 꼬리 단어를 정해야 조합이 성립한다",
  basis="공통표준용어 미등재(exact 0건, 8차 20251101) — 말미 형식단어(수심/깊이) 미확정",
  review="draft")
d("MD-025", "측정결과적합여부", "Compliance Result", "-", "", "boolean", "quality", "",
  "부산 약수터 '검사결과'에서 '적합'/'부적합' 2값 관측. 표준 '적합여부'의 도메인 여부C1은 "
  "'Y : 여(예), N : 부(아니요)' 1자리이므로 적재 시 변환이 필요하다. 경기 "
  "MESURE_RESLT_SUITBLT_YN의 실제 값은 미확인",
  "공통표준용어 미등재(용어명·이음동의어 exact 0건, 8차 20251101). 포함관계 상위어 "
  "'적합여부' STBLT_YN(여부C1, 1차 2020-08)에서 개념을 차용. '측정결과'라는 수식어가 "
  "무엇의 적합인지를 담고 있어 이름은 유지한다. abbr은 비운다 — 표준 자신이 수식어가 붙으면 "
  "약어를 확장한다(위생상태적합여부 SNTT_STTS_STBLT_YN). domain도 비운다 — 관측값이 "
  "여부C1 사양을 위반하므로 변환 규칙 확정 전에는 채우지 않는다. 검사여부(MD-031)와 같은 형태",
  basis="공통표준용어 '적합여부' 차용", review="verified")
d("MD-026", "초과항목명", "Exceeded Item Name", "-", "", "text", "quality", "",
  "기준 초과 항목을 문자열로 담는다 — 측정항목 사전과 대조해 파싱 가능",
  "공통표준용어 미등재(용어명·이음동의어 exact 0건, 8차 20251101) — 차용 대상 미확정: "
  "경기 EXCESS_ITEM_NM의 실제 응답값을 확보하지 못해 한 건만 담는지 구분자로 여러 건을 "
  "묶는지 알 수 없다. 단일이면 '항목명' ARTCL_NM(명V100), 다건이면 '항목내용' "
  "ARTCL_CN(내용V4000) 계열로 차용 대상 자체가 달라진다. "
  "'초과' 접두 등재 용어 12건의 약어 토큰은 전부 EXCS이며 EXCS_ARTCL로 시작하는 약어는 0건",
  basis="공통표준용어 미등재(exact 0건, 8차 20251101) — 값 카디널리티 미확인으로 차용 대상 미확정",
  review="draft")
d("MD-031", "검사여부", "Inspection Performed", "INSP_YN", "여부C1", "boolean", "quality", "",
  "'검사'/'미검사' 2값. 측정 실시 자체의 여부이며 결과 적합여부(MD-025)와 다르다",
  "공통표준용어 등재 확인(8차 20251101, exact match). 설명: 사실이나 일의 상태 또는 물질의 "
  "구성 성분 따위를 조사하여 옳고 그름과 낫고 못함을 판단하는 일을 실시했는지 여부")
d("MD-032", "미검사사유", "Non-Inspection Reason", "-", "", "text", "quality", "",
  "자유 서술 텍스트. 코드화되어 있지 않다",
  "검사여부(MD-031)가 미검사일 때만 채워진다. 부산 약수터 데이터에서 확인. "
  "공통표준용어 미등재(exact 0건, 8차 20251101). 공통표준단어 '미'·'미검사' 모두 미등재라 "
  "조합 불가 — 표준은 未+행위를 단일 단어로 등재한다(미사용 UNSD, 미납 UNPAID, 미결 PND). "
  "근접 용어 '미사용사유' UNSD_RSN(내용V4000)은 개념이 다르다. 표준 미비로 해소 불가",
  basis="공통표준용어·표준단어 미등재 — 소스 관행", review="draft")
d("MD-027", "행번호", "Row Number", "-", "", "integer", "record", "",
  "API 응답 봉투 필드. 데이터 자체의 의미는 없다",
  "공통표준용어 미등재(exact 0건, 8차 20251101). 공통표준단어 '행'도 미등재라 조합 불가. "
  "표준의 행 순번 관용은 '~일련번호'(SN 종결)이나 bare '일련번호' 용어는 없다. "
  "표준 미비이므로 다음 개정 전까지 기관표준용어로 두는 것이 최종 상태다",
  basis="공통표준용어·표준단어 미등재 — 소스 관행", review="draft")
d("MD-028", "전체결과수", "Total Count", "WHOL_RSLT_CNT", "수", "integer", "record", "",
  "API 페이징 메타",
  "공통표준용어 미등재(exact 0건, 8차 20251101). 꼬리 '수'·'결과수' 미등재라 조합으로 간다. "
  "현행 공통표준단어 전체 WHOL + 결과 RSLT + 수 CNT(형식단어) 조합, 동음이의 없음, 충돌 0건. "
  "다만 말미를 '수'(CNT)로 둘지 '건수'(NOCS)로 바꿀지 미결 — 표준 등재 관용은 건수 쪽이고"
  "(전체건수 WHOL_NOCS·결과건수 RSLT_NOCS 둘 다 현행, RSLT+CNT 조합 용어는 0건), "
  "'전체결과건수'로 정하면 등재용어 '결과건수'가 꼬리가 되어 차용으로 판정이 바뀐다. "
  "외부 자료 없이 팀 규칙만 정하면 해소된다",
  basis="공통표준용어 미등재 — 공통표준단어 조합(기관표준용어)", review="draft")
d("MD-029", "자료기준일자", "Data Reference Date", "DATA_CRTR_YMD", "연월일C8", "date",
  "record", "YYYY-MM-DD",
  "관측일이 아니라 파일 갱신일이다. 측정일자(MD-006)와 절대 혼동하면 안 된다",
  "'데이터기준일자'는 공통표준용어에 없다(0건). '데이터'는 공통표준단어에도 없고 "
  "'자료'=DATA가 정식이므로 표준명을 '자료기준일자'로 맞췄다. 실데이터 컬럼은 "
  "'데이터기준일자'로 오므로 동의어로 등록")

# ---------------------------------------------------------------------------
# 4. term_synonyms — (표준코드, 표기, 출처, 유형, 검수상태, 근거스니펫)
#    collected_on은 전부 COLLECTED. 실측 근거는 이전 조사에서 원문 대조 완료.
# ---------------------------------------------------------------------------
S = []


def s(code, surface, src, stype="column_name", review="verified", snippet="", note=""):
    S.append(dict(code=code, surface=surface, source_id=src,
                  collected_on=COLLECTED, synonym_type=stype,
                  review_status=review, evidence_snippet=snippet, note=note))


# --- 국립환경과학원 API (77필드 명세 실측) ----------------------------------
NIER = [
    ("WQ-001", "itemBod"), ("WQ-002", "itemToc"), ("WQ-003", "itemCod"),
    ("WQ-004", "itemSs"), ("WQ-005", "itemTn"), ("WQ-006", "itemTp"),
    ("WQ-008", "itemPh"), ("WQ-009", "itemTemp"), ("WQ-010", "itemCol"),
    ("WQ-011", "itemTcoli"), ("WQ-013", "itemNhex"), ("WQ-014", "itemAbs"),
    ("WQ-015", "itemPhenol"), ("WQ-016", "itemCn"), ("WQ-017", "itemCr"),
    ("WQ-018", "itemCr6"), ("WQ-019", "itemCd"), ("WQ-020", "itemHg"),
    ("WQ-021", "itemPb"), ("WQ-022", "itemAs"), ("WQ-023", "itemCu"),
    ("WQ-024", "itemZn"), ("WQ-025", "itemFe"), ("WQ-026", "itemMn"),
    ("WQ-027", "itemFl"), ("WQ-028", "itemOp"), ("WQ-029", "itemPcb"),
    ("WQ-032", "itemTce"), ("WQ-033", "itemPce"), ("WQ-034", "itemBenzene"),
    ("WQ-035", "itemDcm"), ("WQ-036", "itemDceth"), ("WQ-037", "itemChcl3"),
    ("WQ-038", "itemDiox"), ("WQ-039", "itemHcho"), ("WQ-045", "itemSe"),
    ("WQ-046", "itemBa"), ("WQ-048", "itemCcl4"), ("WQ-050", "itemNi"),
    ("WQ-051", "itemDehp"), ("WQ-059", "itemAntimon"), ("WQ-060", "itemDoc"),
    ("WQ-061", "itemCloa"), ("WQ-062", "itemEc"), ("WQ-063", "itemEcoli"),
    ("WQ-064", "itemNh3n"), ("WQ-065", "itemNo3n"), ("WQ-066", "itemPop"),
    ("WQ-067", "itemDtn"), ("WQ-068", "itemDtp"), ("WQ-073", "itemTrans"),
    ("WQ-074", "itemLvl"), ("WQ-075", "itemAmnt"), ("WQ-076", "itemHcb"),
]
for code, sfc in NIER:
    s(code, sfc, "NIER_WQ_API", snippet="출력결과 명세표 항목명(영문) 열")

# 명세 원문의 오류 — 사전에 남겨 둬야 파이프라인이 속지 않는다
S[[i for i, x in enumerate(S) if x["surface"] == "itemPhenol"][0]]["note"] = (
    "명세의 국문 설명이 'n-Hex 추출물질'로 itemNhex와 중복 기재됨(원문 오류). "
    "필드명 기준으로 페놀류에 매핑")
S[[i for i, x in enumerate(S) if x["surface"] == "itemSe"][0]]["note"] = (
    "명세의 국문 설명이 '세슘'으로 기재됨(원문 오류). 필드명 Se 기준으로 셀레늄에 매핑")
S[[i for i, x in enumerate(S) if x["surface"] == "itemDceth"][0]]["note"] = (
    "명세 국문은 '1,2-다이클로로에탄'인데 코드는 1,1-DCE로 읽힐 소지 — 국문 설명 기준 매핑")

NIER_META = [
    ("MD-001", "ptNm"), ("MD-002", "ptNo"), ("MD-015", "addr"),
    ("MD-022", "orgNm"), ("MD-008", "wmyr"), ("MD-009", "wmod"),
    ("MD-010", "wmwk"), ("MD-006", "wmcymd"), ("MD-024", "wmdep"),
    ("MD-027", "rowno"), ("MD-028", "totalCount"),
]
for code, sfc in NIER_META:
    s(code, sfc, "NIER_WQ_API", snippet="출력결과 명세표 항목명(영문) 열")
for sfc in ("latDgr", "latMin", "latSec"):
    s("MD-013", sfc, "NIER_WQ_API", note="도/분/초 분리 필드 — 십진도 환산 필요")
for sfc in ("lonDgr", "lonMin", "lonSec"):
    s("MD-014", sfc, "NIER_WQ_API", note="도/분/초 분리 필드 — 십진도 환산 필요")

# --- 서울 열린데이터광장 (실제 API 응답 JSON) -------------------------------
SEOUL = [("WQ-009", "WATT"), ("WQ-008", "TOT_PH"), ("WQ-060", "TOT_DO"),
         ("WQ-005", "TOT_N"), ("WQ-006", "TOT_TP"), ("WQ-002", "TOT_OC"),
         ("WQ-030", "PHNL"), ("WQ-016", "CN")]
for code, sfc in SEOUL:
    s(code, sfc, "SEOUL_WPOS",
      snippet='{"YMD":"20260805","HR":"20:00","MSRSTN_NM":"탄천","WATT":"32.1",...}')
S[[i for i, x in enumerate(S) if x["surface"] == "WATT"][0]]["note"] = (
    "도메인 지식 없이는 전력(Watt)으로 오해하기 쉬운 축약 — 사전 없이는 자동 매핑 불가한 대표 사례")
for code, sfc in [("MD-006", "YMD"), ("MD-012", "HR"), ("MD-001", "MSRSTN_NM")]:
    s(code, sfc, "SEOUL_WPOS", snippet="실제 API 응답 row 키")

# --- 전북 CSV (헤더 실측) ---------------------------------------------------
JB = [("WQ-009", "수온"), ("WQ-008", "수소이온농도"), ("WQ-060", "용존산소"),
      ("WQ-001", "생화학적 산소요구량"), ("WQ-003", "화학적 산소요구량"),
      ("WQ-004", "부유물질"), ("WQ-005", "총질소"), ("WQ-006", "총인")]
for code, sfc in JB:
    s(code, sfc, "DATAGO_JB",
      snippet="연도,월,시도 명,시군구 명,읍면동 명,동리 명,측정소 명,수온,수소이온농도,...")
for code, sfc in [("MD-008", "연도"), ("MD-009", "월"), ("MD-017", "시도 명"),
                  ("MD-018", "시군구 명"), ("MD-020", "읍면동 명"),
                  ("MD-021", "동리 명"), ("MD-001", "측정소 명")]:
    s(code, sfc, "DATAGO_JB", snippet="CSV 헤더 1행", note="공백을 포함한 한글 컬럼명")

# --- 제주 CSV ---------------------------------------------------------------
JEJU = [("WQ-009", "온도"), ("WQ-008", "수소이온농도"), ("WQ-001", "생물화학적산소요구량"),
        ("WQ-003", "화학적산소요구량"), ("WQ-002", "총 유기탄소"), ("WQ-004", "부유물질"),
        ("WQ-060", "용존산소"), ("WQ-006", "총인"), ("WQ-011", "총대장균군"),
        ("WQ-063", "분원성대장균군"), ("WQ-007", "생태독성(TU)")]
for code, sfc in JEJU:
    s(code, sfc, "DATAGO_JEJU",
      snippet="해당연도,하천명,구분,시료채취일,온도,수소이온농도,생물화학적산소요구량,...")
for code, sfc in [("MD-008", "해당연도"), ("MD-003", "하천명"), ("MD-011", "시료채취일"),
                  ("MD-022", "관련부서"), ("MD-029", "데이터기준일자")]:
    s(code, sfc, "DATAGO_JEJU", snippet="CSV 헤더 1행")

# --- 안양시 CSV -------------------------------------------------------------
ANYANG = [("WQ-009", "수온"), ("WQ-060", "용존산소량"), ("WQ-001", "생물학적 산소요구량"),
          ("WQ-003", "화학적 산소요구량"), ("WQ-004", "부유물질"), ("WQ-006", "총인"),
          ("WQ-002", "총유기탄소"), ("WQ-008", "수소이온농도"), ("WQ-015", "페놀류"),
          ("WQ-062", "전기전도도"), ("WQ-011", "총대장균군수"), ("WQ-065", "질산성 질소"),
          ("WQ-068", "용존총인"), ("WQ-066", "인산염인"), ("WQ-061", "클로로필"),
          ("WQ-063", "분원성대장균군수")]
for code, sfc in ANYANG:
    s(code, sfc, "DATAGO_ANYANG",
      snippet="측정소명,년,월,수온,용존산소량,생물학적 산소요구량,...,총소질소,총인,...")
s("WQ-005", "총소질소", "DATAGO_ANYANG", stype="typo",
  snippet="...부유물질,총소질소,총인,총유기탄소,...",
  note="'총질소'의 오타가 원본 CSV에 그대로 유통 중. 오타를 사전에 등록해야 이 데이터가 매칭된다")
for code, sfc in [("MD-001", "측정소명"), ("MD-008", "년"), ("MD-009", "월"),
                  ("MD-029", "데이터기준일자")]:
    s(code, sfc, "DATAGO_ANYANG", snippet="CSV 헤더 1행")

# --- 김해시 CSV (단위를 컬럼명에 포함) --------------------------------------
GIMHAE = [("WQ-001", "생물학적 산소요구량(BOD_L당mg)"), ("WQ-002", "총유기탄소(TOC_L당mg)"),
          ("WQ-004", "부유물질량(SS_L당mg)"), ("WQ-005", "총 질소(T-N_L당mg)"),
          ("WQ-006", "총 인(T-P_L당mg)")]
for code, sfc in GIMHAE:
    s(code, sfc, "DATAGO_GIMHAE",
      snippet="하천명,소재지,생물학적 산소요구량(BOD_L당mg),총유기탄소(TOC_L당mg),...",
      note="단위를 컬럼명 안에 넣은 사례 — 정규화 시 괄호를 지우면 다른 항목과 충돌할 수 있어 표기 그대로 보존")
for code, sfc in [("MD-003", "하천명"), ("MD-015", "소재지"), ("MD-011", "시료채취일")]:
    s(code, sfc, "DATAGO_GIMHAE", snippet="CSV 헤더 1행")

# --- 인천 CSV (wide 피벗) ---------------------------------------------------
# 동의어를 등록하지 않는다. '시천천_심곡천수온'처럼 하천명이 병합된 컬럼명은
# pipeline/mapper.py의 _composite_lookup()이 접두어를 떼어 처리한다 (2026-08-06).
#
# 여기에 동의어로 넣으면 안 되는 이유가 두 가지다.
#  1) 지점명이 전국 표준 사전에 들어간다. 인천만 12지점 × 8항목 = 96건이고,
#     다음 지자체 파일마다 같은 양이 또 쌓인다.
#  2) 같은 지점의 컬럼이 갈린다. 동의어로 잡힌 것은 지점 없이 'WQ-009'가 되고
#     파싱 규칙으로 잡힌 것은 'WQ-003@시천천심곡천'이 되어 출력이 어긋난다.

# --- 당진시 / 부산 (상수도·약수터) ------------------------------------------
for code, sfc in [("WQ-071", "일반세균"), ("WQ-011", "총대장균군"),
                  ("WQ-008", "수소이온농도"), ("WQ-069", "탁도")]:
    s(code, sfc, "DATAGO_DANGJIN", snippet="번호,접수일,규격명,채수지,위치,결과,일반세균,...")
for code, sfc in [("WQ-071", "일반세균 중온"), ("WQ-011", "총대장균군"),
                  ("WQ-063", "분원성대장균군"), ("WQ-064", "암모니아성 질소"),
                  ("WQ-065", "질산성 질소"), ("WQ-072", "과망간산칼륨소비량")]:
    s(code, sfc, "DATAGO_BUSAN",
      snippet="번호,공동시설명,검사여부,미검사사유,검사일자,검사결과,일반세균 중온,...")
# 부산 약수터의 관측 메타 — 값을 실제로 확인하고 붙인 것들 (2026-08-06)
for code, sfc, why in [
    ("MD-004", "공동시설명", "약수터는 정수장이 아니라 공동이용시설이라 시설명 계열로 본다"),
    ("MD-006", "검사일자", "값이 YYYY-MM-DD 날짜임을 실데이터로 확인"),
    ("MD-025", "검사결과", "고유값이 '적합'/'부적합' 2종뿐이므로 측정치가 아니라 적합여부 판정이다"),
    ("MD-031", "검사여부", "고유값 '검사'/'미검사' 2종"),
    ("MD-032", "미검사사유", "값 예: '수량부족', '12.23일 지정해제'"),
]:
    s(code, sfc, "DATAGO_BUSAN", review="draft",
      snippet="번호,공동시설명,검사여부,미검사사유,검사일자,검사결과,...", note=why)

# --- 경기데이터드림 ---------------------------------------------------------
for code, sfc in [("WQ-008", "PH_ITEM_VL"), ("WQ-069", "TUBDTY_ITEM_VL"),
                  ("WQ-070", "RSDLCR_ITEM_VL")]:
    s(code, sfc, "GG_WATER_API",
      snippet="<PH_ITEM_VL>7.4102</PH_ITEM_VL><TUBDTY_ITEM_VL>0.0507</TUBDTY_ITEM_VL>",
      note="'<항목약어>_ITEM_VL' 패턴 — 접미사 규칙으로 후보 추출 가능")
for code, sfc in [("MD-007", "OCCUR_DE_TM"), ("MD-019", "SIGUN_CD"), ("MD-018", "SIGUN_NM"),
                  ("MD-004", "FACLT_NM"), ("MD-005", "FACLT_NO"),
                  ("MD-015", "LOCPLC_ADDR"), ("MD-023", "USWTR_DIV_NM")]:
    s(code, sfc, "GG_WATER_API", snippet="메타 JSON columns[].colId")
for code, sfc in [("MD-008", "SUM_YY"), ("MD-018", "SIGUN_NM"), ("MD-030", "SPOT_NO"),
                  ("MD-011", "WATRSMPL_DE"), ("MD-025", "MESURE_RESLT_SUITBLT_YN"),
                  ("MD-026", "EXCESS_ITEM_NM"), ("MD-016", "REFINE_ROADNM_ADDR"),
                  ("MD-015", "REFINE_LOTNO_ADDR"), ("MD-013", "REFINE_WGS84_LAT"),
                  ("MD-014", "REFINE_WGS84_LOGT"), ("MD-019", "SIGUN_CD")]:
    s(code, sfc, "GG_SPRING_API", snippet="상세페이지 출력필드 명세 19개")

# --- 표준명 변경으로 사라진 구 표기 보존 --------------------------------------
# 공통표준용어 대조(8차 20251101) 결과 표준명을 바꾼 항목의 옛 이름.
# 남기지 않으면 옛 표기를 쓰는 기관 파일이 매핑에서 조용히 누락된다.
s("MD-004", "측정시설명", "MANUAL", stype="deprecated_std_name",
  note="2026-08-08 표준용어 '시설명' 채택으로 대체된 구 표준명")
s("MD-005", "측정시설번호", "MANUAL", stype="deprecated_std_name",
  note="2026-08-08 표준용어 '시설번호' 채택으로 대체된 구 표준명")

# --- 법령 내부의 표기 변형 (같은 법령 안에서 다르게 적힌 것) ------------------
s("WQ-001", "생물화학적 산소요구량", "LAW_ANNEX13", stype="legal_variant",
  snippet="가목 2) 표: '생물화학적산소요구량(㎎/L)'과 '생물화학적 산소요구량(㎎/L)'이 같은 표에 병존",
  note="법령 원문조차 한 표 안에서 띄어쓰기가 흔들린다")
s("WQ-029", "폴리클로리네이티드바이페닐(PCB)함유량", "LAW_ANNEX13", stype="legal_variant",
  snippet="나목 8) 2019.1.1~2020.12.31 기준표",
  note="현행(2021~) 표기는 'PCB함유량'으로 축약됨")
s("WQ-027", "플루오르(불소)함유량", "LAW_ANNEX13", stype="legal_variant", review="draft",
  note="PDF 텍스트 추출 결과는 '플로오르(불소)'. 정오표 가능성 있어 국가법령정보센터 원문 재확인 필요")
s("WQ-023", "구리함유량", "LAW_ANNEX13", stype="legal_variant",
  snippet="나목 1) 2007년 기준표는 '구리함유량', 2011년 이후는 '구리(동)함유량'")
s("WQ-011", "총대장균군수", "LAW_ANNEX13", stype="legal_variant",
  snippet="총대장균군(群)(총대장균군수)(㎖)")

# --- 별표 3(특정수질유해물질 목록)의 표기 -----------------------------------
# 같은 법(물환경보전법 시행규칙) 안에서도 별표 3과 별표 13의 물질 표기가 다르다.
for _code, (_no, _name) in sorted(TOXIC.items(), key=lambda kv: kv[1][0]):
    _std = next(r["std_name"] for r in M if r["code"] == _code)
    if _name != _std:
        s(_code, _name, "LAW_ANNEX3", stype="legal_variant",
          snippet="별표 3 제%d호" % _no,
          note="특정수질유해물질 목록의 정본 표기. 별표 13의 '%s'과 같은 물질" % _std)

# --- 환경정책기본법 시행령 별표 1(환경기준)의 표기 ---------------------------
# 물환경보전법과 환경정책기본법이 같은 물질을 다르게 적는다. 사전 없이는 통합 불가.
ENV_VARIANTS = [
    ("WQ-008", "수소이온농도(pH)", "하천 생활환경 기준", ""),
    ("WQ-001", "생물화학적산소요구량(BOD)", "하천 생활환경 기준", ""),
    ("WQ-003", "화학적산소요구량(COD)", "하천 생활환경 기준", "비고 4에 따라 2015.12.31까지 적용"),
    ("WQ-003", "화학적 산소요구량(COD)", "하천 생활환경 기준 비고 제4호",
     "같은 별표 안에서 표 머리글은 붙여쓰고 비고는 띄어 쓴다"),
    ("WQ-002", "총유기탄소량(TOC)", "하천 생활환경 기준", ""),
    ("WQ-004", "부유물질량(SS)", "하천 생활환경 기준", ""),
    ("WQ-060", "용존산소량(DO)", "하천 생활환경 기준", ""),
    ("WQ-006", "총인(total phosphorus)", "하천 생활환경 기준",
     "하천은 영문 병기, 호소는 '총인(㎎/L)'로 병기 없음"),
    ("WQ-005", "총질소(total nitrogen)", "호소 생활환경 기준",
     "하천 기준에는 총질소가 없다 — 호소에만 있는 항목"),
    ("WQ-061", "클로로필-a(Chl-a)", "호소 생활환경 기준", ""),
    ("WQ-019", "카드뮴(Cd)", "하천 사람의 건강보호 기준", ""),
    ("WQ-022", "비소(As)", "하천 사람의 건강보호 기준", ""),
    ("WQ-016", "시안(CN)", "하천 사람의 건강보호 기준", "수치 상한이 아니라 '검출되어서는 안 됨'"),
    ("WQ-020", "수은(Hg)", "하천 사람의 건강보호 기준", "'검출되어서는 안 됨'"),
    ("WQ-028", "유기인", "하천 사람의 건강보호 기준", "'검출되어서는 안 됨'"),
    ("WQ-029", "폴리클로리네이티드비페닐(PCB)", "하천 사람의 건강보호 기준",
     "별표 13은 '바이페닐', 환경기준은 '비페닐' — 한 글자 차이로 문자열 매칭이 깨진다"),
    ("WQ-021", "납(Pb)", "하천 사람의 건강보호 기준", ""),
    ("WQ-018", "6가 크롬(Cr6+)", "하천 사람의 건강보호 기준",
     "환경기준은 '6가 크롬'(공백), 별표 13은 '6가크롬함유량'(붙임). "
     "같은 별표 1의 해역 기준에서는 '6가크로뮴'으로 또 다르게 적는다"),
    ("WQ-014", "음이온 계면활성제(ABS)", "하천 사람의 건강보호 기준",
     "환경기준은 '음이온 계면활성제'(공백), 별표 13은 '음이온계면활성제'(붙임)"),
    ("WQ-048", "사염화탄소", "하천 사람의 건강보호 기준", ""),
    ("WQ-049", "1,2-디클로로에탄", "하천 사람의 건강보호 기준",
     "별표 3은 '1, 2-디클로로에탄'(콤마 뒤 공백), 환경기준·별표 13은 공백 없음"),
    ("WQ-033", "테트라클로로에틸렌(PCE)", "하천 사람의 건강보호 기준", ""),
    ("WQ-035", "디클로로메탄", "하천 사람의 건강보호 기준", ""),
    ("WQ-034", "벤젠", "하천 사람의 건강보호 기준", ""),
    ("WQ-037", "클로로포름", "하천 사람의 건강보호 기준", ""),
    ("WQ-051", "디에틸헥실프탈레이트(DEHP)", "하천 사람의 건강보호 기준", ""),
    ("WQ-059", "안티몬", "하천 사람의 건강보호 기준", ""),
    ("WQ-038", "1,4-다이옥세인", "하천 사람의 건강보호 기준",
     "환경기준은 '다이옥세인', 별표 13은 '다이옥산'. 두 법령이 같은 물질을 다르게 표기한다"),
    ("WQ-039", "포름알데히드", "하천 사람의 건강보호 기준",
     "환경기준은 '포름알데히드', 별표 13은 '폼알데하이드'. 두 법령이 같은 물질을 다르게 표기한다"),
    ("WQ-076", "헥사클로로벤젠", "하천 사람의 건강보호 기준", ""),
    ("WQ-011", "총대장균군", "하천 생활환경 기준",
     "환경기준 단위는 군수/100mL, 별표 13은 군수/㎖ — 값을 그대로 비교하면 안 된다"),
    ("WQ-063", "분원성대장균군", "하천 생활환경 기준", ""),
]
for _code, _sfc, _where, _note in ENV_VARIANTS:
    s(_code, _sfc, "LAW_ENV_STD", stype="legal_variant",
      snippet="환경정책기본법 시행령 별표 1 — " + _where, note=_note)

# --- 먹는물 수질기준(제3의 표기 계열) ---------------------------------------
# 배출허용기준·환경기준에 이어 세 번째 법령 계열. 같은 물질을 또 다르게 적는다.
DRINK_VARIANTS = [
    ("WQ-008", "수소이온 농도", "제5호 사목",
     "먹는물 기준은 '수소이온 농도'(공백), 별표 13·환경기준은 '수소이온농도'(붙임)"),
    ("WQ-011", "총 대장균군", "제1호 나목",
     "먹는물 기준은 '총 대장균군'(공백), 별표 13·환경기준은 '총대장균군'(붙임). "
     "같은 수도법령 안에서도 시행규칙 제22조의4는 '총대장균군'으로 붙여 쓴다"),
    ("WQ-063", "대장균·분원성 대장균군", "제1호 다목",
     "먹는물 기준은 대장균과 분원성대장균군을 한 항목으로 묶는다 — 1:1 매핑이 성립하지 않는 사례"),
    ("WQ-063", "분원성 대장균군", "제1호 다목", "공백 있는 표기"),
    ("WQ-071", "저온일반세균", "제1호 가목", "샘물·염지하수에 적용되는 세분 항목"),
    ("WQ-071", "중온일반세균", "제1호 가목",
     "부산 약수터 데이터의 '일반세균 중온'이 여기 대응한다"),
    ("WQ-027", "불소", "제2호 나목",
     "먹는물 기준의 법령 표기는 '불소'(1.5㎎/L). 별표 13은 '플로오르(불소)함유량' — "
     "초안이 동의어로 넣었던 '불소'는 실제 법령 표기였다"),
    ("WQ-056", "크실렌", "제3호 머목",
     "먹는물 기준은 '크실렌', 별표 13은 '자일렌'. 같은 물질(Xylene)의 두 법령 표기"),
    ("WQ-023", "동", "제5호 라목",
     "먹는물 기준은 '동'(1㎎/L), 별표 13은 '구리(동)함유량'"),
    ("WQ-014", "세제(음이온 계면활성제)", "제5호 바목",
     "먹는물 기준은 '세제'를 표제어로 쓰고 계면활성제를 괄호에 넣는다"),
    ("WQ-016", "시안", "제2호 바목", ""),
    ("WQ-017", "크롬", "제2호 사목", ""),
    ("WQ-030", "페놀", "제3호 가목", ""),
    ("WQ-039", "포름알데히드", "제4호 카목",
     "먹는물 기준도 환경기준과 같은 '포름알데히드'. 별표 13만 '폼알데하이드'다"),
    ("WQ-038", "1,4-다이옥산", "제3호 서목", "먹는물 기준은 별표 13과 같은 '다이옥산'"),
    ("WQ-055", "톨루엔", "제3호 러목", ""),
    ("WQ-069", "탁도", "제5호 파목", ""),
    ("WQ-010", "색도", "제5호 마목", ""),
]
for _code, _sfc, _ho, _note in DRINK_VARIANTS:
    s(_code, _sfc, "LAW_DRINKING", stype="legal_variant",
      snippet="먹는물 수질기준 및 검사 등에 관한 규칙 별표 1 " + _ho, note=_note)

s("WQ-070", "유리잔류염소", "LAW_WATERWORKS", stype="legal_variant",
  snippet="수도법 시행규칙 제22조의2제1항제3호: '수도꼭지의 먹는물 유리잔류염소가 항상 "
          "0.1밀리그램/리터(결합잔류염소는 0.4밀리그램/리터) 이상이 되도록 할 것'",
  note="하한 기준 조문. 단위를 '㎎/L'가 아니라 한글 '밀리그램/리터'로 적는다")
s("WQ-070", "잔류염소", "LAW_WATERWORKS", stype="legal_variant",
  snippet="수도법 시행규칙 제22조의4제3항제1호: '잔류염소: 리터당 0.1밀리그램 이상 4.0밀리그램 이하'",
  note="저수조 청소 후 점검 기준. 여기서는 괄호 정의문 없이 '잔류염소'로만 쓴다")
s("WQ-008", "수소이온농도(pH)", "LAW_WATERWORKS", stype="legal_variant",
  snippet="수도법 시행규칙 제22조의4제3항제2호",
  note="같은 개념을 먹는물검사규칙은 '수소이온 농도', 수도법 시행규칙은 '수소이온농도(pH)'로 적는다")

# --- 공공데이터 공통표준용어에 등재된 수질 항목 -----------------------------
# '수질' 포함 용어는 0건이지만 개별 항목은 등재돼 있다. 영문약어가 곧 권장 컬럼명이다.
for _code, _abbr, _dom in [("WQ-008", "HION_DNST", "수N8,3 (7차)"),
                           ("WQ-004", "SSQTY", "수N10,3 (8차)"),
                           ("WQ-062", "ELCD", "")]:
    s(_code, _abbr, "MOIS_STD_TERM", stype="abbreviation",
      snippet="공통표준용어 영문약어명 = " + _abbr + (" / " + _dom if _dom else ""),
      note="행정안전부 공통표준용어의 공식 영문약어. 새 테이블 컬럼명은 이걸 따르는 게 맞다")

# 관측 메타의 표준 영문약어 — 매칭이 약어로도 걸리도록 동의어에 넣는다
for _code, _abbr in [("MD-001", "MSRSTN_NM"), ("MD-003", "RVR_NM"),
                     ("MD-006", "MSRMT_YMD"), ("MD-007", "MSRMT_DT"),
                     ("MD-011", "SPCM_PCKNG_YMD"), ("MD-011", "WTSMP_YMD"),
                     ("MD-013", "LAT"), ("MD-014", "LOT"),
                     ("MD-015", "LCTN_ADDR"), ("MD-016", "ROAD_NM_ADDR"),
                     ("MD-017", "CTPV_NM"), ("MD-018", "SGG_NM"),
                     ("MD-019", "STDG_SGG_CD"), ("MD-019", "STDG_CD"),
                     ("MD-022", "INST_NM"), ("MD-029", "DATA_CRTR_YMD")]:
    s(_code, _abbr, "MOIS_STD_TERM", stype="abbreviation",
      snippet="공통표준용어 영문약어명 = " + _abbr)

# MD-030은 채택이 아니라 미확정이다. MSPT_NO는 '측정지점번호'에 배정된 약어이므로
# 우리 약어로 오독되지 않게 review=draft로 두고 근거를 명시한다.
s("MD-030", "MSPT_NO", "MOIS_STD_TERM", stype="abbreviation", review="draft",
  snippet="공통표준용어 '측정지점번호'의 영문약어명",
  note="차용 후보의 약어일 뿐 우리 용어에 배정된 약어가 아니다. 개념 동일성 확인 전까지 미검수")

# --- 초안(AI 생성) 동의어: 출처를 정직하게 표시하고 미검수로 둔다 ------------
DRAFT = [
    ("WQ-001", ["BOD5", "생물학적 산소요구량", "비오디"]),
    ("WQ-002", ["총유기탄소", "티오씨"]),
    ("WQ-003", ["CODMn", "CODCr", "씨오디"]),
    ("WQ-004", ["부유물질", "현탁물질", "에스에스"]),
    ("WQ-005", ["TN", "T_N", "총 질소"]),
    ("WQ-006", ["TP", "T_P", "총 인"]),
    ("WQ-007", ["독성단위", "물벼룩 급성독성"]),
    ("WQ-008", ["산도", "피에이치", "수소이온지수"]),
    ("WQ-009", ["수온", "온도(℃)"]),
    ("WQ-011", ["대장균군"]),
    ("WQ-012", ["노르말헥산추출물질"]),
    ("WQ-014", ["MBAS", "계면활성제(음이온)"]),
    ("WQ-015", ["페놀류화합물"]),
    ("WQ-016", ["시안화물", "CN-"]),
    ("WQ-017", ["총크롬"]),
    ("WQ-018", ["육가크롬", "Cr-VI"]),
    ("WQ-019", ["카드뮴화합물"]),
    ("WQ-020", ["수은화합물"]),
    ("WQ-021", ["연", "납화합물"]),
    ("WQ-022", ["비소화합물"]),
    ("WQ-023", ["동", "구리화합물"]),
    ("WQ-024", ["아연화합물"]),
    ("WQ-025", ["용존철"]),
    ("WQ-026", ["용존망간"]),
    # '불소'는 먹는물 수질기준의 실제 법령 표기라 LAW_DRINKING 쪽에 등록했다
    ("WQ-027", ["플루오린", "플루오르", "F-"]),
    ("WQ-028", ["유기인화합물"]),
    ("WQ-029", ["PCBs", "폴리염화비페닐"]),
    ("WQ-030", ["석탄산"]),
    ("WQ-032", ["트리클로로에텐"]),
    ("WQ-033", ["퍼클로로에틸렌", "테트라클로로에텐"]),
    ("WQ-035", ["염화메틸렌", "메틸렌클로라이드"]),
    ("WQ-036", ["1,1-디클로로에텐"]),
    ("WQ-037", ["트리클로로메탄"]),
    # '1,4-다이옥세인'과 '포름알데히드'는 초안이 AI 표기로 넣었지만 실제로는
    # 환경정책기본법 시행령 별표 1의 법령 표기였다. LAW_ENV_STD 쪽에 등록했으므로 여기서 뺀다.
    ("WQ-038", ["다이옥산"]),
    ("WQ-044", ["스타이렌"]),
    ("WQ-045", ["셀렌"]),
]
for code, lst in DRAFT:
    for sfc in lst:
        s(code, sfc, "DRAFT_AI", stype="colloquial", review="draft",
          note="초안 xlsx의 AI 생성 표기 — 실데이터/법령에서 확인되기 전까지 미검수")

# --- 검토 후 폐기한 동의어 -------------------------------------------------
# 매핑 엔진은 괄호 안 내용을 약어 후보로 따로 색인한다. 그래서 괄호를 떼면
# 서로 다른 항목이 같은 문자열이 되는 표기는 사전에 두면 안 된다.
for _code, _sfc, _why in [
    ("WQ-005", "질소(총)", "괄호를 떼면 '질소', 괄호부는 '총' — WQ-006 '인(총)'과 충돌"),
    ("WQ-006", "인(총)", "괄호를 떼면 '인', 괄호부는 '총' — WQ-005 '질소(총)'과 충돌"),
    ("WQ-012", "유분(광유)", "괄호를 떼면 '유분' — WQ-013 '유분(동식물유지)'과 충돌"),
    ("WQ-013", "유분(동식물유지)", "괄호를 떼면 '유분' — WQ-012 '유분(광유)'과 충돌"),
    ("WQ-018", "Cr(VI)", "괄호를 떼면 'Cr' — 총크롬(WQ-017)의 약어와 충돌. 'Cr-VI'로 대체"),
]:
    s(_code, _sfc, "DRAFT_AI", stype="colloquial", review="rejected",
      note="사전에서 폐기: " + _why)


# ---------------------------------------------------------------------------
# 5. 출력
# ---------------------------------------------------------------------------
M_COLS = ["code", "std_name", "name_en", "abbr", "unit", "category", "legal_basis",
          "legal_article", "legal_effective_from", "legal_revision", "legal_status",
          "is_toxic_substance", "toxic_substance_basis", "source_url", "review_status",
          "reviewed_by", "reviewed_at", "note"]
D_COLS = ["code", "std_name", "name_en", "abbr", "std_domain", "value_type", "facet",
          "standard_basis", "source_url", "canonical_format", "normalization_note",
          "review_status", "reviewed_by", "reviewed_at", "note"]
SRC_COLS = ["source_id", "source_name", "organization", "source_type", "base_url",
            "access_note", "encoding", "reliability"]
SYN_COLS = ["term_kind", "measurement_code", "metadata_code", "surface", "source_id",
            "collected_on", "evidence_url", "evidence_snippet", "synonym_type",
            "review_status", "note"]

SRC_URL = {r[0]: r[4] for r in SOURCES}


def syn_rows():
    for r in S:
        kind = "measurement" if r["code"].startswith("WQ-") else "metadata"
        yield {
            "term_kind": kind,
            "measurement_code": r["code"] if kind == "measurement" else "",
            "metadata_code": r["code"] if kind == "metadata" else "",
            "surface": r["surface"],
            "source_id": r["source_id"],
            "collected_on": r["collected_on"],
            "evidence_url": SRC_URL.get(r["source_id"]) or "",
            "evidence_snippet": r["evidence_snippet"],
            "synonym_type": r["synonym_type"],
            "review_status": r["review_status"],
            "note": r["note"],
        }


def write_csv(path, cols, rows):
    with open(os.path.join(OUT, path), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: ("" if r.get(c) is None else r.get(c, "")) for c in cols})


def sql_lit(v):
    if v is None or v == "":
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    return "'" + str(v).replace("'", "''") + "'"


def main():
    src_rows = [dict(zip(SRC_COLS, r)) for r in SOURCES]
    syns = list(syn_rows())

    write_csv("measurement_terms.csv", M_COLS, M)
    write_csv("metadata_terms.csv", D_COLS, D)
    write_csv("term_sources.csv", SRC_COLS, src_rows)
    write_csv("term_synonyms.csv", SYN_COLS, syns)

    # --- seed.sql -----------------------------------------------------------
    lines = [
        "-- 수질 표준사전 시드 데이터",
        f"-- 생성: build_dictionary.py / 근거 수집일 {COLLECTED}",
        "-- 적용 순서: schema.sql -> seed.sql",
        "BEGIN;", "",
        "-- 1. 출처 레지스트리",
    ]
    for r in src_rows:
        lines.append(
            "INSERT INTO term_sources (%s) VALUES (%s) ON CONFLICT (source_id) DO NOTHING;"
            % (", ".join(SRC_COLS), ", ".join(sql_lit(r[c]) for c in SRC_COLS)))

    lines += ["", "-- 2. 측정항목 사전"]
    mc = [c for c in M_COLS if c not in ("reviewed_at",)]
    for r in M:
        lines.append("INSERT INTO measurement_terms (%s) VALUES (%s);"
                     % (", ".join(mc), ", ".join(sql_lit(r[c]) for c in mc)))

    lines += ["", "-- 3. 관측 메타 사전"]
    dc = [c for c in D_COLS if c not in ("reviewed_at",)]
    for r in D:
        lines.append("INSERT INTO metadata_terms (%s) VALUES (%s);"
                     % (", ".join(dc), ", ".join(sql_lit(r[c]) for c in dc)))

    lines += ["", "-- 4. 동의어 (출처·수집일 포함)"]
    sc = [c for c in SYN_COLS if c != "term_kind"]
    for r in syns:
        lines.append("INSERT INTO term_synonyms (%s) VALUES (%s);"
                     % (", ".join(sc), ", ".join(sql_lit(r[c]) for c in sc)))

    lines += ["", "COMMIT;", ""]
    with open(os.path.join(OUT, "seed.sql"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # --- 요약 ---------------------------------------------------------------
    print(f"measurement_terms : {len(M):3d}행  "
          f"(현행법정 {sum(1 for r in M if r['legal_status']=='statutory')}, "
          f"구법정 {sum(1 for r in M if r['legal_status']=='superseded')}, "
          f"비법정 {sum(1 for r in M if r['legal_status']=='non_statutory')})")
    print(f"metadata_terms    : {len(D):3d}행")
    print(f"term_sources      : {len(src_rows):3d}행")
    print(f"term_synonyms     : {len(syns):3d}행  "
          f"(검수완료 {sum(1 for r in syns if r['review_status']=='verified')}, "
          f"미검수 {sum(1 for r in syns if r['review_status']=='draft')})")

    # 무결성 체크: 존재하지 않는 표준코드를 가리키는 동의어
    codes = {r["code"] for r in M} | {r["code"] for r in D}
    orphans = sorted({r["surface"] + "->" + (r["measurement_code"] or r["metadata_code"])
                      for r in syns
                      if (r["measurement_code"] or r["metadata_code"]) not in codes})
    if orphans:
        print("!! 표준코드 없는 동의어:", orphans)

    # 한 표기가 두 코드에 붙은 경우
    from collections import defaultdict
    norm = defaultdict(set)
    for r in syns:
        key = "".join(ch for ch in r["surface"].lower() if ch.isalnum())
        norm[key].add(r["measurement_code"] or r["metadata_code"])
    conflicts = {k: v for k, v in norm.items() if len(v) > 1}
    if conflicts:
        print("!! 동일 표기가 복수 코드에 매핑:")
        for k, v in sorted(conflicts.items()):
            print("   ", k, sorted(v))


if __name__ == "__main__":
    main()
