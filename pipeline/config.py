"""매핑 엔진 설정값.

임계값은 검증 데이터로 조정할 것이므로 반드시 여기서만 관리한다.
코드 어디에도 하드코딩하지 말 것.
"""

# ── 유사도 임계값 (rapidfuzz fuzz.ratio, 0~100) ──────────────────────────
# score >= FUZZY_AUTO_THRESHOLD          → 자동 채택 (fuzzy_auto)
# FUZZY_REVIEW_THRESHOLD <= score < AUTO → 확인 대기열 (needs_review)
# score < FUZZY_REVIEW_THRESHOLD         → unmapped
FUZZY_AUTO_THRESHOLD = 85
FUZZY_REVIEW_THRESHOLD = 70

# ── 경로 (프로젝트 루트 기준 상대경로) ───────────────────────────────────
ONTOLOGY_DIR = "ontology"
MEASUREMENT_DICT_FILENAME = "measurement_terms.csv"
METADATA_DICT_FILENAME = "metadata_terms.csv"
OUTPUT_DIR = "output"

# ── 헤더 자동 탐지: 파일 상단 몇 행까지 헤더 후보로 볼지 ─────────────────
HEADER_SCAN_ROWS = 5

# ── 병합 헤더 복원 ───────────────────────────────────────────────────────
# 헤더 위쪽 행을 '그룹 헤더'로 인정할 최소 라벨 수.
# 2로 두면 제목 한 줄(셀 1개)은 제외되고 여러 칸에 흩어진 그룹 라벨만 끌어온다.
MERGED_HEADER_MIN_LABELS = 2

# ── CSV 읽기 시 시도할 인코딩 순서 ───────────────────────────────────────
CSV_ENCODINGS = ("utf-8-sig", "cp949", "euc-kr")

# unmapped 컬럼에 붙일 접두어
UNMAPPED_PREFIX = "UNMAPPED_"

# ── 복합 컬럼명 분해 ('{지점명}_{측정항목}') ─────────────────────────────
# 사전 exact로 인정할 항목 꼬리의 최소 정규화 길이.
# 1로 낮추면 한 글자 꼬리가 우연히 사전에 걸려 엉뚱한 코드가 붙는다.
COMPOSITE_MIN_TAIL_LEN = 2

# 출력 컬럼명에서 표준코드와 지점 라벨을 잇는 구분자 (WQ-009@공촌천)
SITE_SEPARATOR = "@"
