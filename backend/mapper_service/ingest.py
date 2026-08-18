"""가로형 파일을 세로형 측정값 레코드로 편다.

    원본 : 강정천 | 2024-03-14 | 온도 16.7 | BOD 0.6
    출력 : (강정천, 2024-03-14, WQ-009, 16.7)
           (강정천, 2024-03-14, WQ-001, 0.6)

파이썬이 이 일을 맡는 이유: 파일을 여는 것도 컬럼을 판정하는 것도 여기서 하는데,
값만 자바로 넘겨 다시 파싱하게 하면 인코딩·헤더 탐지 로직이 두 벌이 된다.
스프링은 정제된 레코드를 받아 저장만 한다.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterator

import pandas as pd

# ─────────────────────────────────────────────────────────────────
# 컬럼의 '역할' — 표준코드로 정한다.
# 우선순위 순서다. 앞의 것이 있으면 그것을 쓴다.
# ─────────────────────────────────────────────────────────────────
SITE_CODES = ("MD-034", "MD-001", "MD-003", "MD-004")   # 사업장명 > 측정소명 > 하천명 > 시설명
OUTLET_CODES = ("MD-033",)                                # 방류구
DATE_CODES = ("MD-011", "MD-006", "MD-041", "MD-029")     # 시료채취일자 > 측정일자 > 분석일
DATETIME_CODES = ("MD-007",)                              # 측정일시
YEAR_CODES = ("MD-008",)                                  # 측정연도
MONTH_CODES = ("MD-009",)                                 # 측정월
PERIOD_CODES = ("MD-010",)                                # 측정회차 (1분기 등)
LIMIT_CODES = ("MD-054", "MD-055")                        # 배출허용기준 · 방류수수질기준

# ⚠ 원폐수/방류수 구분은 표준 사전에 아직 용어가 없다(2026-08-11 확인).
#   코드로 잡을 수 없어 원본 컬럼명으로 임시 인식한다.
#   사전에 등재되면 이 목록을 지우고 코드 기반으로 바꾼다.
SAMPLE_TYPE_RAW_NAMES = ("시료구분", "시료종류", "채수구분")
SAMPLE_TYPE_VALUES = {"원폐수", "방류수", "유입수", "처리수", "방류", "원수"}

# 숫자로 볼 수 없는 값들. 버리지 않고 원문을 남긴다.
NON_NUMERIC_MARKERS = {"불검출", "검출안됨", "n.d.", "nd", "-", "–", "없음", "미검출", "해당없음"}

_NUMERIC_RE = re.compile(r"^[<>≤≥]?\s*(-?\d+(?:\.\d+)?)\s*$")
_DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d",
                 "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S")


@dataclass
class ColumnRole:
    """어느 컬럼이 무슨 역할인지. 매핑 결과에서 뽑아 둔다."""
    site: int | None = None
    outlet: int | None = None
    date: int | None = None
    datetime_: int | None = None
    year: int | None = None
    month: int | None = None
    period: int | None = None
    sample_type: int | None = None
    # 측정항목 컬럼: index -> 표준코드
    measurements: dict[int, str] = None
    # 기준치 컬럼: 어느 항목의 기준인가(항목명 라벨) -> index
    limits: dict[str, int] = None

    def __post_init__(self):
        if self.measurements is None:
            self.measurements = {}
        if self.limits is None:
            self.limits = {}


def resolve_roles(columns: list[dict], frame: pd.DataFrame) -> ColumnRole:
    """매핑 결과를 훑어 컬럼 역할을 정한다.

    기준치 컬럼은 복합 컬럼명 분해 덕에 어느 항목의 것인지 라벨이 남아 있다.
    '생물화학적산소요구량 배출허용기준' → code=MD-054, site='생물화학적산소요구량'
    엔진의 site 필드가 여기서는 지점명이 아니라 항목명을 담는다.
    """
    roles = ColumnRole()

    def take(field: str, codes: tuple[str, ...], index: int, code: str) -> bool:
        if code in codes and getattr(roles, field) is None:
            setattr(roles, field, index)
            return True
        return False

    for col in columns:
        index = col.get("column_index")
        code = col.get("code")
        raw = col.get("raw") or ""

        # 사전에 용어가 없는 축은 컬럼명으로 인식한다 (임시)
        if roles.sample_type is None and any(n in raw for n in SAMPLE_TYPE_RAW_NAMES):
            roles.sample_type = index
            continue

        if not code:
            # 판정되지 않은 컬럼이라도 값이 원폐수/방류수뿐이면 시료구분으로 본다
            if roles.sample_type is None and index is not None and index < frame.shape[1]:
                values = frame.iloc[:, index].dropna().astype(str).str.strip()
                uniques = set(values.unique())
                if uniques and uniques <= SAMPLE_TYPE_VALUES:
                    roles.sample_type = index
            continue

        if code in LIMIT_CODES:
            label = col.get("site") or raw
            roles.limits[label] = index
            continue

        if col.get("dict_type") == "측정항목":
            roles.measurements[index] = code
            continue

        for field, codes in (("site", SITE_CODES), ("outlet", OUTLET_CODES),
                             ("date", DATE_CODES), ("datetime_", DATETIME_CODES),
                             ("year", YEAR_CODES), ("month", MONTH_CODES),
                             ("period", PERIOD_CODES)):
            if take(field, codes, index, code):
                break

    return roles


def cell(frame: pd.DataFrame, row: int, index: int | None) -> str | None:
    if index is None or index >= frame.shape[1]:
        return None
    value = frame.iat[row, index]
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    text = str(value).strip()
    return text or None


def parse_number(text: str | None) -> tuple[float | None, str]:
    """값을 숫자로 바꾼다. 못 바꾸면 이유를 함께 돌려준다.

    '<0.001' 처럼 부등호가 붙은 정량한계 미만 표기가 실제로 온다.
    숫자만 떼어 쓰되 원문은 따로 보존한다.
    """
    if text is None:
        return None, "empty"
    if text.lower() in NON_NUMERIC_MARKERS:
        return None, "non_numeric"
    cleaned = text.replace(",", "")
    match = _NUMERIC_RE.match(cleaned)
    if not match:
        return None, "non_numeric"
    return float(match.group(1)), "ok"


def parse_date(text: str | None) -> date | None:
    if not text:
        return None
    head = text.split(" ")[0]
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(head, fmt).date()
        except ValueError:
            continue
    return None


def resolve_date(frame: pd.DataFrame, row: int, roles: ColumnRole) -> tuple[date | None, str | None]:
    """흩어진 날짜 컬럼을 하나의 축으로 합친다.

    파일마다 표기가 제각각이다. 제주는 '시료채취일' 한 칸,
    충남은 '측정년월'과 '회차'가 따로 있다.
    """
    for index in (roles.date, roles.datetime_):
        parsed = parse_date(cell(frame, row, index))
        if parsed:
            return parsed, None

    # 연·월이 따로 있으면 합친다. 일자는 알 수 없으므로 1일로 둔다.
    year_text = cell(frame, row, roles.year)
    if year_text:
        year_value, _ = parse_number(year_text)
        month_value, _ = parse_number(cell(frame, row, roles.month) or "")
        if year_value:
            month = int(month_value) if month_value and 1 <= month_value <= 12 else 1
            try:
                return date(int(year_value), month, 1), cell(frame, row, roles.period)
            except ValueError:
                pass

    return None, cell(frame, row, roles.period)


def quality_of(value: float | None, reason: str, measured_on: date | None) -> str | None:
    """품질 경고.

    ⚠ TMS 고시 별표 1(비정상자료 선별기준)을 아직 확보하지 못했다.
      지금은 누구나 동의할 최소 규칙만 적용한다. 별표를 받으면 법이 정한
      기준으로 교체해야 한다 — 그때 '우리가 정했다'가 '법이 정한 방식'이 된다.
    """
    if reason == "non_numeric":
        return "non_numeric"
    if measured_on and measured_on > date.today():
        return "future_date"
    if value is not None and value < 0:
        return "negative"
    return None


def iter_records(frame: pd.DataFrame, columns: list[dict]) -> Iterator[dict]:
    """세로형 레코드를 하나씩 내보낸다.

    전부 메모리에 쌓지 않고 흘려보낸다. 104만 행짜리 파일에서 측정항목이
    여섯이면 레코드가 600만 개가 되는데, 한 번에 만들면 메모리가 감당하지 못한다.
    """
    roles = resolve_roles(columns, frame)
    raw_by_index = {c.get("column_index"): (c.get("raw") or "") for c in columns}

    for row in range(len(frame)):
        site = cell(frame, row, roles.site)
        outlet = cell(frame, row, roles.outlet)
        sample_type = cell(frame, row, roles.sample_type)
        measured_on, period = resolve_date(frame, row, roles)

        for index, code in roles.measurements.items():
            text = cell(frame, row, index)
            if text is None:
                continue  # 빈칸은 적재하지 않는다. 없는 것과 0은 다르다.

            value, reason = parse_number(text)
            source_column = raw_by_index.get(index, "")

            # 이 항목에 딸린 기준치 컬럼이 있으면 함께 싣는다.
            # 라벨은 항목명이므로 컬럼명에 그 항목명이 들어 있는지로 맞춘다.
            reported_limit = None
            for label, limit_index in roles.limits.items():
                if label and label.replace(" ", "") in source_column.replace(" ", ""):
                    limit_value, _ = parse_number(cell(frame, row, limit_index))
                    reported_limit = limit_value
                    break

            yield {
                "source_row": row,
                "source_column": source_column,
                "source_column_index": index,
                "site_name": site,
                "outlet": outlet,
                "sample_type": sample_type,
                "measured_on": measured_on.isoformat() if measured_on else None,
                "period_label": period,
                "item_code": code,
                "value_num": value,
                "value_text": text[:100],
                "is_numeric": value is not None,
                "reported_limit": reported_limit,
                "quality_flag": quality_of(value, reason, measured_on),
            }
