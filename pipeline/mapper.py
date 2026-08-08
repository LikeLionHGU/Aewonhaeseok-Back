"""수질 데이터 컬럼 매핑 엔진.

설계 원칙: 판단은 사전과 규칙이 한다. 유사도는 후보 제안만 한다. 최종 확정은 사람이 한다.

매핑 순서 (반드시 이 순서):
  0단계  normalize()       — 모든 비교 전에 공통 적용
  1단계  사전 정확 일치     — 본체 exact → 괄호 추출 약어 exact. 일치 즉시 확정, 점수 없음
  1.5단계 복합 컬럼명 분해   — '{지점명}_{측정항목}'에서 항목 꼬리 exact. 지점명은 라벨로 보존
  2단계  유사도 후보 제안   — rapidfuzz. 임계값은 config.py에서만 관리
  3단계  llm_fallback()    — 훅만 존재, NotImplementedError
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

from . import config


# ═════════════════════════════════════════════════════════════════════════
# 0단계 — 정규화
# ═════════════════════════════════════════════════════════════════════════

# 괄호(반각 기준; NFKC가 전각 괄호를 반각으로 바꿔줌) 안 내용 추출
_PAREN_RE = re.compile(r"\(([^()]*)\)")
# 본체에서 제거할 구분자류. 괄호부 토큰 분리에서는 하이픈을 살린다("T-N" 보존).
_SEP_RE = re.compile(r"[\s_\-·.,;:/\\]+")
_PAREN_TOKEN_SPLIT_RE = re.compile(r"[\s_/,;·+&]+")
_TOKEN_CLEAN_RE = re.compile(r"[\s\-_.]+")
_NUMBER_TOKEN_RE = re.compile(r"^\d+(?:\.\d+)?$")

# 괄호부 토큰이 순수 단위 표기인지 (mg/L, ㎎/L, L당mg, ℃→°c, TU, NTU, %, µS/cm …)
_UNIT_TOKEN_RE = re.compile(
    r"^(?:"
    r"(?:mg|㎎|ug|µg|μg|ng|g)(?:/|당)?l?"
    r"|l당mg|mg당l|mgl|l"
    r"|°c|℃"
    r"|tu|ntu|jtu"
    r"|cfu(?:/?\d*ml)?|mpn(?:/?\d*ml)?"
    r"|%|퍼센트|psu"
    r"|(?:µ|u|μ)s/?cm"
    r"|\d+(?:\.\d+)?(?:ml|㎖)?"
    r"|개(?:/?ml)?"
    r")$"
)

# 본체 끝에 붙은 단위 표기 제거용 (구분자 제거 후의 형태 기준, 끝에서 반복 제거)
_TRAILING_UNIT_RE = re.compile(
    r"(?:"
    r"(?:mg|㎎|ug|µg|μg|ng)당?l?"
    r"|l당mg|mg당l"
    r"|°c"
    r"|ntu|jtu|tu"
    r"|cfu(?:\d*ml)?|mpn(?:\d*ml)?"
    r"|%|퍼센트|psu"
    r"|(?:µ|u|μ)scm"
    r")$"
)


@dataclass(frozen=True)
class NormalizedName:
    """정규화 결과. 원본 문자열(raw)은 감사 기록용으로 절대 버리지 않는다."""

    raw: str                      # 원본 그대로
    body: str                     # 괄호를 뗀 본체의 정규화 형태
    paren_tokens: tuple[str, ...] # 괄호 안에서 추출한 약어 후보 (단위 표기는 제거됨)

    @property
    def display(self) -> str:
        """report에 기록할 정규화명."""
        if self.paren_tokens:
            return f"{self.body}({'|'.join(self.paren_tokens)})"
        return self.body


def _clean_token(token: str) -> str:
    return _TOKEN_CLEAN_RE.sub("", token).lower()


def _strip_trailing_units(body: str) -> str:
    while True:
        m = _TRAILING_UNIT_RE.search(body)
        if not m:
            return body
        stripped = body[: m.start()]
        if stripped == body:
            return body
        body = stripped


def normalize(text: object) -> NormalizedName:
    """컬럼명/사전 표기 공통 정규화.

    - 전각→반각(NFKC), 영문 소문자 통일
    - 괄호와 괄호 안 내용은 분리 보관 (괄호부는 약어 매칭에 쓰므로 버리지 않음)
    - 공백/언더스코어/하이픈 등 구분자 제거
    - 단위 표기 패턴 제거 (본체 꼬리 + 괄호부 토큰)
    """
    raw = "" if text is None else str(text)
    s = unicodedata.normalize("NFKC", raw).strip()

    # 괄호부 분리 보관 (중첩 없는 그룹 반복 추출)
    paren_groups: list[str] = []
    body_src = s
    while True:
        groups = _PAREN_RE.findall(body_src)
        if not groups:
            break
        paren_groups.extend(groups)
        body_src = _PAREN_RE.sub("", body_src)

    # 본체 정규화: 소문자 → 구분자 제거 → 꼬리 단위 제거
    body = body_src.lower()
    body = _SEP_RE.sub("", body)
    body = _strip_trailing_units(body)

    # 괄호부 토큰화: 하이픈은 살려서 분리("T-N" 보존) 후 토큰 단위 정규화,
    # 단위 표기 토큰과 순수 숫자 토큰은 버림 → 남는 것이 약어 후보
    tokens: list[str] = []
    for group in paren_groups:
        for tok in _PAREN_TOKEN_SPLIT_RE.split(group.lower()):
            tok = tok.strip()
            if not tok:
                continue
            if _UNIT_TOKEN_RE.match(tok) or _NUMBER_TOKEN_RE.match(tok):
                continue
            cleaned = _clean_token(tok)
            if cleaned and not _UNIT_TOKEN_RE.match(cleaned) and not _NUMBER_TOKEN_RE.match(cleaned):
                tokens.append(cleaned)

    return NormalizedName(raw=raw, body=body, paren_tokens=tuple(tokens))


# ═════════════════════════════════════════════════════════════════════════
# 사전 로딩
# ═════════════════════════════════════════════════════════════════════════

DICT_MEASUREMENT = "측정항목"
DICT_METADATA = "메타"

_VARIANT_FIELDS = ("name_ko", "name_en", "abbr")


class DictionaryConflictError(ValueError):
    """같은 표기가 서로 다른 코드(특히 두 사전 모두)에 걸리는 사전 품질 문제.

    숨기지 말고 즉시 실패시킨다.
    """


@dataclass(frozen=True)
class DictEntry:
    dict_type: str      # 측정항목 | 메타
    code: str
    field: str          # name_ko / name_en / abbr / synonyms / …(paren)
    variant: str        # 사전에 적힌 원 표기
    variant_norm: str   # normalize().body 기준 정규화 표기


@dataclass
class Lexicon:
    """두 사전의 모든 표기를 정규화해 색인한 조회 구조."""

    entries: list[DictEntry] = field(default_factory=list)
    exact_index: dict[str, DictEntry] = field(default_factory=dict)
    fuzzy_choices: list[str] = field(default_factory=list)

    def add(self, entry: DictEntry) -> None:
        existing = self.exact_index.get(entry.variant_norm)
        if existing is not None:
            if (existing.dict_type, existing.code) != (entry.dict_type, entry.code):
                raise DictionaryConflictError(
                    f"사전 표기 충돌: '{entry.variant}'(정규화 '{entry.variant_norm}') 가 "
                    f"[{existing.dict_type}] {existing.code} 와 [{entry.dict_type}] {entry.code} "
                    f"모두에 존재합니다. 사전을 먼저 정리하세요."
                )
            return  # 같은 코드의 중복 표기는 무해 → 무시
        self.exact_index[entry.variant_norm] = entry
        self.entries.append(entry)
        self.fuzzy_choices.append(entry.variant_norm)


def _iter_variants(row: pd.Series) -> list[tuple[str, str]]:
    """사전 한 행에서 (필드명, 표기) 쌍을 모두 뽑는다."""
    variants: list[tuple[str, str]] = []
    for f in _VARIANT_FIELDS:
        v = str(row.get(f, "") or "").strip()
        if v and v.lower() != "nan":
            variants.append((f, v))
    syn = str(row.get("synonyms", "") or "").strip()
    if syn and syn.lower() != "nan":
        for v in syn.split("|"):
            v = v.strip()
            if v:
                variants.append(("synonyms", v))
    return variants


def _load_one_dict(path: Path, dict_type: str, lexicon: Lexicon) -> None:
    df = pd.read_csv(path, dtype=str).fillna("")
    if "code" not in df.columns:
        raise ValueError(f"{path}: 'code' 컬럼이 없습니다. 사전 형식을 확인하세요.")
    for _, row in df.iterrows():
        code = str(row["code"]).strip()
        if not code:
            continue
        for fname, variant in _iter_variants(row):
            norm = normalize(variant)
            if norm.body:
                lexicon.add(DictEntry(dict_type, code, fname, variant, norm.body))
            # 사전 표기 자체에 괄호 약어가 있으면 그것도 색인 (예: "클로로필-a(Chl-a)")
            for tok in norm.paren_tokens:
                lexicon.add(DictEntry(dict_type, code, f"{fname}(paren)", variant, tok))


def load_lexicon(measurement_path: Path | str, metadata_path: Path | str) -> Lexicon:
    """두 표준 사전을 로딩하고 사전 간/사전 내 표기 충돌을 검증한다."""
    lexicon = Lexicon()
    _load_one_dict(Path(measurement_path), DICT_MEASUREMENT, lexicon)
    _load_one_dict(Path(metadata_path), DICT_METADATA, lexicon)
    return lexicon


# ═════════════════════════════════════════════════════════════════════════
# 1·2단계 — 매핑
# ═════════════════════════════════════════════════════════════════════════

STATUS_EXACT = "exact"
STATUS_FUZZY_AUTO = "fuzzy_auto"
STATUS_NEEDS_REVIEW = "needs_review"
STATUS_UNMAPPED = "unmapped"

AUTO_STATUSES = (STATUS_EXACT, STATUS_FUZZY_AUTO)


@dataclass
class MappingResult:
    norm: NormalizedName
    status: str
    code: str | None = None            # exact/fuzzy_auto에서만 확정 코드
    dict_type: str | None = None
    matched_variant: str | None = None # 매칭(또는 후보)된 사전 표기 원문
    matched_norm: str | None = None
    score: float | None = None         # exact는 None (점수 없음)
    via: str | None = None             # body | paren | composite
    candidate_code: str | None = None  # needs_review 후보
    site: str | None = None            # 복합 컬럼명에서 떼어낸 지점 라벨

    @property
    def raw(self) -> str:
        return self.norm.raw

    @property
    def adopted(self) -> bool:
        return self.status in AUTO_STATUSES


def _exact_lookup(lexicon: Lexicon, norm: NormalizedName) -> MappingResult | None:
    # 본체 exact
    if norm.body:
        hit = lexicon.exact_index.get(norm.body)
        if hit is not None:
            return MappingResult(
                norm=norm, status=STATUS_EXACT, code=hit.code, dict_type=hit.dict_type,
                matched_variant=hit.variant, matched_norm=hit.variant_norm, via="body",
            )
    # 괄호부에서 추출한 약어 exact (예: "생물학적 산소요구량(BOD_L당mg)" → BOD)
    for tok in norm.paren_tokens:
        hit = lexicon.exact_index.get(tok)
        if hit is not None:
            return MappingResult(
                norm=norm, status=STATUS_EXACT, code=hit.code, dict_type=hit.dict_type,
                matched_variant=hit.variant, matched_norm=hit.variant_norm, via="paren",
            )
    return None


def _composite_lookup(lexicon: Lexicon, norm: NormalizedName) -> MappingResult | None:
    """'{지점명}{구분자}{측정항목}' 형태의 복합 컬럼명을 분해한다.

    인천시 파일처럼 하천명이 컬럼명에 병합된 wide 구조를 위한 규칙이다.
    통째로 비교하면 지점명이 유사도를 희석시켜 사전에 정확히 있는 항목까지
    needs_review로 떨어진다("공촌천_수소이온농도" → 80점).

    구분자 위치로 자르지 않고 꼬리 후보를 전부 훑는 이유: 실데이터에 구분자가
    빠진 표기("시천천_심곡천수온")와 엉뚱한 자리에 붙은 표기("나진포_천용존산소")가
    함께 들어 있다. 구분자를 믿으면 둘 다 놓친다.

    사전 exact 일치만 인정한다. 여기서 유사도까지 허용하면 접두어를 잘라 만든
    조각이 아무 항목에나 걸려 억지 매칭이 된다.
    """
    raw = norm.raw
    for cut in range(1, len(raw)):
        tail = normalize(raw[cut:])
        if len(tail.body) < config.COMPOSITE_MIN_TAIL_LEN:
            break  # 꼬리는 짧아지기만 하므로 더 볼 것이 없다
        hit = lexicon.exact_index.get(tail.body)
        if hit is None:
            continue
        site = _SEP_RE.sub("", raw[:cut])
        if not site:
            continue
        return MappingResult(
            norm=norm, status=STATUS_EXACT, code=hit.code, dict_type=hit.dict_type,
            matched_variant=hit.variant, matched_norm=hit.variant_norm,
            via="composite", site=site,
        )
    return None


def _fuzzy_lookup(lexicon: Lexicon, norm: NormalizedName) -> MappingResult:
    queries = [("body", norm.body)] + [("paren", t) for t in norm.paren_tokens]
    queries = [(via, q) for via, q in queries if q]
    if not queries or not lexicon.fuzzy_choices:
        return MappingResult(norm=norm, status=STATUS_UNMAPPED)

    best: tuple[float, str, str] | None = None  # (score, matched_norm, via)
    for via, q in queries:
        found = process.extractOne(q, lexicon.fuzzy_choices, scorer=fuzz.ratio)
        if found is None:
            continue
        matched_norm, score, _ = found
        if best is None or score > best[0]:
            best = (score, matched_norm, via)

    if best is None:
        return MappingResult(norm=norm, status=STATUS_UNMAPPED)

    score, matched_norm, via = best
    score = round(float(score), 1)
    entry = lexicon.exact_index[matched_norm]

    if score >= config.FUZZY_AUTO_THRESHOLD:
        return MappingResult(
            norm=norm, status=STATUS_FUZZY_AUTO, code=entry.code, dict_type=entry.dict_type,
            matched_variant=entry.variant, matched_norm=matched_norm, score=score, via=via,
        )
    if score >= config.FUZZY_REVIEW_THRESHOLD:
        return MappingResult(
            norm=norm, status=STATUS_NEEDS_REVIEW, dict_type=entry.dict_type,
            matched_variant=entry.variant, matched_norm=matched_norm, score=score, via=via,
            candidate_code=entry.code,
        )
    # 임계값 미만: 후보를 채택하지도, 제안하지도 않는다 (억지 매칭 금지)
    return MappingResult(norm=norm, status=STATUS_UNMAPPED, score=score)


def map_column(name: object, lexicon: Lexicon) -> MappingResult:
    """컬럼명 하나를 매핑한다. 1단계(exact) → 1.5단계(복합 분해) → 2단계(fuzzy) 순서 고정.

    복합 분해를 fuzzy보다 앞에 두는 이유: 분해로 얻는 것은 사전 exact 일치라
    점수 기반 추정보다 근거가 강하다. 순서가 뒤집히면 확실한 판정을 추정이 가린다.
    """
    norm = normalize(name)
    exact = _exact_lookup(lexicon, norm)
    if exact is not None:
        return exact
    composite = _composite_lookup(lexicon, norm)
    if composite is not None:
        return composite
    return _fuzzy_lookup(lexicon, norm)


# ═════════════════════════════════════════════════════════════════════════
# 파일 읽기 + 헤더 자동 탐지
# ═════════════════════════════════════════════════════════════════════════

_EXCEL_SUFFIXES = {".xlsx", ".xlsm", ".xls"}


def _is_number_like(value: object) -> bool:
    try:
        float(str(value).replace(",", ""))
        return True
    except (TypeError, ValueError):
        return False


def detect_header_row(raw: pd.DataFrame, scan_rows: int = config.HEADER_SCAN_ROWS) -> int:
    """상단 scan_rows 행 중 '헤더다움' 점수가 가장 높은 행을 헤더로 고른다.

    헤더다움 = 비어있지 않고 숫자/날짜가 아닌 문자열 셀 수 (+ 전부 고유하면 가산점).
    동점이면 위쪽 행 우선.
    """
    best_row, best_score = 0, -1
    for i in range(min(scan_rows, len(raw))):
        row = raw.iloc[i]
        values = [v for v in row.tolist() if not pd.isna(v) and str(v).strip() != ""]
        headerish = sum(
            1 for v in values
            if not _is_number_like(v) and not isinstance(v, pd.Timestamp)
        )
        score = headerish
        if headerish and len({str(v) for v in values}) == len(values):
            score += 1
        if score > best_score:
            best_row, best_score = i, score
    return best_row


def _cell(v: object) -> str:
    return "" if pd.isna(v) else str(v).strip()


def _is_group_header_row(values: list[str]) -> bool:
    """병합 헤더의 상위 행인가, 아니면 제목 한 줄인가.

    제목 행은 보통 셀 하나만 차 있다. 그룹 헤더 행은 여러 칸에 라벨이 흩어져 있다.
    이 구분이 없으면 제목 조각이 헤더로 딸려 들어온다.
    """
    return sum(1 for v in values if v) >= config.MERGED_HEADER_MIN_LABELS


def fill_merged_header(raw: pd.DataFrame, header_row: int) -> list[str]:
    """헤더 행의 빈 칸을 위쪽 그룹 헤더에서 끌어온다 (세로 병합 셀 복원).

    엑셀에서 세로로 병합된 셀은 아래 칸이 비어 있다. 헤더 행만 읽으면 그 컬럼이
    통째로 사라진다 — 충남 물환경측정망 파일에서 측정소명·측정소코드가 이렇게 소실됐다.

        1행: 지점명 | 지점번호(PT_NO) | 측정년월/회차 |          |
        2행:        |                 | 년(WMYR)      | 월(WMOD) |   ← 헤더로 선택됨

    빈 칸만 채운다. 이미 값이 있으면 건드리지 않는다 —
    '측정값' 그룹 아래의 '수온(0.0)'을 '측정값수온(0.0)'으로 만들면 안 되기 때문이다.
    위로 올라가다 제목 행(라벨 1개 이하)을 만나면 멈춘다.
    """
    header = [_cell(v) for v in raw.iloc[header_row].tolist()]
    for i in range(header_row - 1, -1, -1):
        above = [_cell(v) for v in raw.iloc[i].tolist()]
        if not _is_group_header_row(above):
            break
        for j, cur in enumerate(header):
            if not cur and j < len(above) and above[j]:
                header[j] = above[j]
        if all(header):
            break
    return header


def read_data_file(path: Path | str) -> tuple[pd.DataFrame, int]:
    """xlsx/csv를 헤더 자동 탐지로 읽는다. 반환: (데이터프레임, 헤더 행 인덱스)."""
    path = Path(path)
    if path.suffix.lower() in _EXCEL_SUFFIXES:
        raw = pd.read_excel(path, header=None)
    else:
        raw = None
        last_err: Exception | None = None
        for enc in config.CSV_ENCODINGS:
            try:
                raw = pd.read_csv(path, header=None, dtype=object, encoding=enc)
                break
            except (UnicodeDecodeError, ValueError) as e:
                last_err = e
        if raw is None:
            raise ValueError(f"{path}: CSV 인코딩을 인식하지 못했습니다 ({last_err})")

    header_row = detect_header_row(raw)
    filled = fill_merged_header(raw, header_row)
    header = [v if v else f"UNNAMED_{j}" for j, v in enumerate(filled)]
    df = raw.iloc[header_row + 1 :].reset_index(drop=True)
    df.columns = header
    return df, header_row


# ═════════════════════════════════════════════════════════════════════════
# 파일 단위 매핑
# ═════════════════════════════════════════════════════════════════════════

@dataclass
class FileMapping:
    path: Path
    header_row: int
    results: list[MappingResult]
    mapped_df: pd.DataFrame

    def summary(self) -> dict:
        total = len(self.results)
        n_auto = sum(1 for r in self.results if r.status in AUTO_STATUSES)
        n_review = sum(1 for r in self.results if r.status == STATUS_NEEDS_REVIEW)
        n_unmapped = sum(1 for r in self.results if r.status == STATUS_UNMAPPED)
        pct = (lambda n: round(100.0 * n / total, 1) if total else 0.0)
        return {
            "전체 컬럼 수": total,
            "자동 매핑 수": n_auto,
            "확인 필요 수": n_review,
            "실패 수": n_unmapped,
            "자동 매핑률": pct(n_auto),
            "확인 필요율": pct(n_review),
            "실패율": pct(n_unmapped),
        }


def output_column_name(r: MappingResult) -> str:
    """매핑 결과 하나가 출력 CSV에서 가질 컬럼명.

    복합 컬럼명은 코드만 쓰면 지점이 다른 같은 항목끼리 이름이 겹친다
    (공촌천_수온, 굴포천_수온 → 둘 다 WQ-009). 지점 라벨을 붙여 구분한다.
    """
    if r.adopted:
        return f"{r.code}{config.SITE_SEPARATOR}{r.site}" if r.site else r.code
    if r.status == STATUS_UNMAPPED:
        return f"{config.UNMAPPED_PREFIX}{r.raw}"
    return r.raw  # needs_review: 사람 확정 전이므로 원본명 유지


def _dedupe(names: list[str]) -> list[str]:
    """중복 컬럼명에 일련번호를 붙인다.

    지점 라벨까지 붙이면 정상 데이터에서는 겹치지 않지만, 원본에 같은 컬럼이
    두 번 있는 경우까지 조용히 덮어쓰게 둘 수는 없다.
    """
    seen: dict[str, int] = {}
    out: list[str] = []
    for n in names:
        seen[n] = seen.get(n, 0) + 1
        out.append(n if seen[n] == 1 else f"{n}#{seen[n]}")
    return out


def map_file(path: Path | str, lexicon: Lexicon) -> FileMapping:
    path = Path(path)
    df, header_row = read_data_file(path)

    results = [map_column(col, lexicon) for col in df.columns]

    mapped_df = df.copy()
    mapped_df.columns = _dedupe([output_column_name(r) for r in results])

    return FileMapping(path=path, header_row=header_row, results=results, mapped_df=mapped_df)


# ═════════════════════════════════════════════════════════════════════════
# 3단계 — LLM fallback (훅만, 구현하지 않음)
# ═════════════════════════════════════════════════════════════════════════

def llm_fallback(column_name: str, dictionary: Lexicon) -> MappingResult:
    """3단계: 사전 exact/유사도 모두 실패한 컬럼명에 대한 LLM 기반 후보 제안 훅.

    설계 의도:
      - 입력: 원본 컬럼명과 표준 사전(Lexicon).
      - 출력: MappingResult — 단, LLM 제안은 절대 자동 채택하지 않고
        status="needs_review"로만 반환해 사람 확정을 거치게 한다.
      - 호출 위치: map_column()에서 STATUS_UNMAPPED 판정 이후 (현재는 미연결).

    지금은 훅만 필요하므로 구현하지 않는다.
    """
    raise NotImplementedError("3단계 LLM fallback은 아직 구현되지 않았습니다 (훅 전용).")
