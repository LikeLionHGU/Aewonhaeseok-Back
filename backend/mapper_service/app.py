"""컬럼명 매핑 서비스.

스프링이 내부에서만 호출한다. 외부에 노출하지 않는다.

매핑 엔진(pipeline/)과 표준 사전(ontology/)은 upstream 저장소가 관리하는 것이라
여기서는 읽기만 하고 절대 고치지 않는다. 사전 업데이트를 git merge로 받아야 하기 때문이다.

    uvicorn app:app --port 8000
"""

from __future__ import annotations

import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator

# pipeline / ontology 를 임포트하려면 저장소 루트가 경로에 있어야 한다.
# backend/mapper_service/app.py → parents[2] 가 저장소 루트다.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd  # noqa: E402
from fastapi import FastAPI, File, Form, HTTPException, UploadFile  # noqa: E402
from fastapi.responses import JSONResponse, StreamingResponse  # noqa: E402

from pipeline import config  # noqa: E402
from ingest import iter_records  # noqa: E402
from pipeline.mapper import (  # noqa: E402
    AUTO_STATUSES,
    DICT_MEASUREMENT,
    DictionaryConflictError,
    Lexicon,
    load_lexicon,
    map_column,
    map_file,
    output_column_name,
    read_data_file,
)
from pipeline.version import (  # noqa: E402
    DictionaryVersion,
    VersionFileMissing,
    load_dictionary_version,
)

ONTOLOGY_DIR = REPO_ROOT / config.ONTOLOGY_DIR
MEASUREMENT_PATH = ONTOLOGY_DIR / config.MEASUREMENT_DICT_FILENAME
METADATA_PATH = ONTOLOGY_DIR / config.METADATA_DICT_FILENAME

EXCEL_SUFFIXES = {".xlsx", ".xlsm", ".xls"}

# 검증 화면에 보여줄 예시 값 개수. 사람이 훑어보고 판단할 만큼만.
SAMPLE_VALUE_LIMIT = 12

# 원본 미리보기 행 수.
PREVIEW_ROW_LIMIT = 10


class State:
    """메모리에 올려둔 사전. 프로세스가 살아 있는 동안 재사용한다.

    사전 적재는 0.02초지만 pandas·rapidfuzz 임포트에 1초 가까이 걸린다.
    요청마다 파이썬을 새로 띄우지 않는 이유가 이것이다.
    """

    lexicon: Lexicon | None = None
    version: DictionaryVersion | None = None


state = State()


def _load() -> None:
    state.lexicon = load_lexicon(MEASUREMENT_PATH, METADATA_PATH)
    try:
        state.version = load_dictionary_version(ONTOLOGY_DIR)
    except VersionFileMissing:
        # VERSION.json이 없어도 매핑은 되어야 한다. 버전만 미상으로 둔다.
        state.version = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    _load()
    yield


app = FastAPI(title="물어볼래 매핑 서비스", lifespan=lifespan)


# ═══════════════════════════════════════════════════════════════════
# 인코딩 판별
# ═══════════════════════════════════════════════════════════════════

def detect_encoding(path: Path) -> str | None:
    """CSV가 어떤 인코딩으로 읽혔는지 알아낸다.

    엔진의 read_data_file()은 인코딩을 폴백으로 시도하지만 어느 것이 통했는지
    돌려주지 않는다. 엔진을 고치지 않기 위해 같은 순서로 여기서 다시 판별한다.
    공공기관 파일은 cp949가 태반이라 화면에 표시할 값이 필요하다.
    """
    if path.suffix.lower() in EXCEL_SUFFIXES:
        return None
    raw = path.read_bytes()
    for encoding in config.CSV_ENCODINGS:
        try:
            raw.decode(encoding)
            return encoding
        except (UnicodeDecodeError, LookupError):
            continue
    return None


# ═══════════════════════════════════════════════════════════════════
# 실제 값 요약
# ═══════════════════════════════════════════════════════════════════

def summarize_values(series: pd.Series) -> dict:
    """컬럼의 실제 값을 요약한다.

    검증 화면에서 필수다. 인천·제주 파일의 '구분'처럼 컬럼명만으로는
    무엇인지 판단할 수 없는 경우가 실제로 있다.

    전부 고유한 값이면 일련번호일 가능성이 높다는 힌트를 함께 준다.
    """
    text = series.dropna().astype(str).str.strip()
    text = text[text != ""]

    distinct = int(text.nunique())
    samples = text.drop_duplicates().head(SAMPLE_VALUE_LIMIT).tolist()

    return {
        "row_count": int(len(series)),
        "distinct_count": distinct,
        "samples": samples,
        "all_unique": bool(len(text) > 0 and distinct == len(text)),
    }


# ═══════════════════════════════════════════════════════════════════
# 응답 변환
# ═══════════════════════════════════════════════════════════════════

def to_column_payload(index: int, result, values: pd.Series | None) -> dict:
    """엔진의 MappingResult를 스프링이 받는 형태로 옮긴다.

    필드 이름은 엔진의 것을 그대로 쓴다. 양쪽 다 snake_case라
    중계 구간에서 키를 변환할 필요가 없다.
    """
    adopted = result.status in AUTO_STATUSES

    payload = {
        "column_index": index,
        "raw": result.raw,
        "normalized": result.norm.display,
        "status": result.status,
        "via": result.via,
        # 자동 확정일 때만 code를 채운다. 후보를 확정처럼 넘기면 안 된다.
        "code": result.code if adopted else None,
        "candidate_code": None if adopted else result.candidate_code,
        "site": result.site,
        "output_column": output_column_name(result),
        "matched_variant": result.matched_variant,
        # exact는 점수가 없다(None). 사전에 정확히 있었다는 뜻이지 100점이 아니다.
        "score": result.score,
        "dict_type": result.dict_type,
    }

    # 값 요약은 사람이 판정해야 하는 컬럼에만 붙인다.
    # 104만 행짜리 파일에서 전 컬럼을 훑으면 느려지는데, 쓰이지도 않는다.
    if values is not None and not adopted:
        payload["value_summary"] = summarize_values(values)

    return payload


def version_payload() -> dict:
    if state.version is None:
        return {"version": "unknown", "content_hash": "", "generated_at": "", "counts": {}}
    return state.version.as_dict()


def parse_overrides(raw: str | None) -> dict[str, dict]:
    """스프링이 보낸 파일별 검토 결과를 요청 시작 전에 검증한다."""
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="overrides must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="overrides must be a JSON object")
    return parsed


def apply_overrides(columns: list[dict], overrides: dict[str, dict]) -> None:
    """사전을 바꾸지 않고 이번 파일의 확정 매핑만 덮어쓴다."""
    for raw_index, override in overrides.items():
        try:
            index = int(raw_index)
        except (TypeError, ValueError):
            continue
        if not (0 <= index < len(columns)) or not isinstance(override, dict):
            continue
        code = override.get("code")
        if not isinstance(code, str) or not code.strip():
            continue
        columns[index]["code"] = code
        if override.get("dict_type") is not None:
            columns[index]["dict_type"] = override["dict_type"]
        columns[index]["status"] = "exact"
        columns[index]["via"] = "review"


# ═══════════════════════════════════════════════════════════════════
# 엔드포인트
# ═══════════════════════════════════════════════════════════════════

@app.get("/health")
def health() -> dict:
    """떠 있는지 확인용. 사전이 올라와 있는지도 함께 본다."""
    return {
        "ok": state.lexicon is not None,
        "dictionary_version": version_payload().get("version"),
        "variants": len(state.lexicon.entries) if state.lexicon else 0,
    }


@app.post("/map")
async def map_upload(file: UploadFile = File(...)) -> JSONResponse:
    """파일 하나를 매핑한다.

    스프링이 파일 경로가 아니라 내용을 보낸다. 두 서비스가 같은 디스크를
    공유한다고 가정하지 않기 위해서다.
    """
    if state.lexicon is None:
        _load()

    filename = file.filename or "upload.csv"
    suffix = Path(filename).suffix.lower() or ".csv"

    # 엔진이 확장자로 csv/xlsx를 구분하므로 원래 확장자를 살려 임시 저장한다.
    with TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir) / f"upload{suffix}"
        temp_path.write_bytes(await file.read())

        encoding = detect_encoding(temp_path)

        try:
            mapping = map_file(temp_path, state.lexicon)
        except DictionaryConflictError as e:
            return JSONResponse(
                status_code=500,
                content={"error": {"code": "DICTIONARY_CONFLICT", "message": str(e)}},
            )
        except ValueError as e:
            # 엔진이 인코딩을 못 잡으면 여기로 온다.
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "code": "FILE_ENCODING_UNSUPPORTED",
                        "message": "CSV 인코딩을 인식하지 못했습니다.",
                        "detail": {"tried": list(config.CSV_ENCODINGS), "cause": str(e)},
                    }
                },
            )

        frame = mapping.mapped_df
        columns = [
            to_column_payload(
                i,
                result,
                frame.iloc[:, i] if i < frame.shape[1] else None,
            )
            for i, result in enumerate(mapping.results)
        ]

    version = version_payload()
    return JSONResponse(content={
        "dictionary_version": version.get("version"),
        "dictionary_hash": version.get("content_hash"),
        "encoding_detected": encoding,
        "header_row": mapping.header_row,
        "columns": columns,
    })


@app.post("/rows")
async def map_rows(
    file: UploadFile = File(...),
    overrides: str | None = Form(None),
) -> StreamingResponse:
    """파일을 세로형 측정값 레코드로 펴서 흘려보낸다.

    응답은 NDJSON(줄마다 JSON 객체 하나)이다. 첫 줄은 요약이고 그다음이 레코드다.
    배열 하나로 감싸지 않는 이유: 104만 행 파일은 레코드가 수백만 개라
    전부 만들어 놓고 보내면 양쪽 메모리가 감당하지 못한다.
    """
    if state.lexicon is None:
        _load()

    filename = file.filename or "upload.csv"
    suffix = Path(filename).suffix.lower() or ".csv"
    content = await file.read()
    parsed_overrides = parse_overrides(overrides)

    def stream() -> Iterator[bytes]:
        with TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / f"upload{suffix}"
            temp_path.write_bytes(content)

            mapping = map_file(temp_path, state.lexicon)
            columns = [
                to_column_payload(i, r, None) for i, r in enumerate(mapping.results)
            ]
            # 스프링에 저장된 최신 매핑(사람 검수 포함)을 재적재에도 그대로 사용한다.
            # 전역 사전은 변경하지 않고 해당 파일에만 적용되는 override다.
            apply_overrides(columns, parsed_overrides)
            version = version_payload()

            measured = sum(
                1 for c in columns
                if c["dict_type"] == DICT_MEASUREMENT and c["code"]
            )
            header = {
                "kind": "meta",
                "dictionary_version": version.get("version"),
                "dictionary_hash": version.get("content_hash"),
                "encoding_detected": detect_encoding(temp_path),
                "header_row": mapping.header_row,
                "source_rows": int(len(mapping.mapped_df)),
                "measured_columns": measured,
            }
            yield (json.dumps(header, ensure_ascii=False) + "\n").encode("utf-8")

            for record in iter_records(mapping.mapped_df, columns):
                record["kind"] = "row"
                yield (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")

    return StreamingResponse(stream(), media_type="application/x-ndjson")


@app.post("/map/column")
def map_single_column(payload: dict) -> dict:
    """컬럼명 하나만 매핑한다. 화면 미리보기용."""
    if state.lexicon is None:
        _load()
    result = map_column(payload.get("name", ""), state.lexicon)
    return to_column_payload(0, result, None)


@app.post("/preview")
async def preview(file: UploadFile = File(...)) -> dict:
    """원본 상위 몇 행을 그대로 돌려준다.

    용어 검증 화면에서 값을 눈으로 확인하는 용도다. 컬럼명만으로는 판단할 수 없는
    경우가 실제로 있어서(인천·제주의 '구분'), 사람이 원본을 봐야 한다.
    """
    filename = file.filename or "upload.csv"
    suffix = Path(filename).suffix.lower() or ".csv"

    with TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir) / f"upload{suffix}"
        temp_path.write_bytes(await file.read())

        frame, header_row = read_data_file(temp_path)
        head = frame.head(PREVIEW_ROW_LIMIT)

        return {
            "header_row": header_row,
            "encoding_detected": detect_encoding(temp_path),
            "total_rows": int(len(frame)),
            "columns": [str(c) for c in frame.columns],
            "rows": [
                ["" if pd.isna(v) else str(v) for v in row]
                for row in head.itertuples(index=False, name=None)
            ],
        }


@app.get("/dictionary/terms")
def dictionary_terms() -> dict:
    """표준코드 → 한글 표준명.

    검증 화면이 후보 코드(MD-006)만 보여주면 사람이 판단할 수 없다.
    '측정일자'까지 함께 보여줘야 한다. '다른 항목 선택' 드롭다운도 이걸 쓴다.
    """
    if state.lexicon is None:
        _load()

    terms: dict[str, dict] = {}
    for entry in state.lexicon.entries:
        # name_ko 필드에서 온 표기가 표준명이다. 동의어는 표준명이 아니다.
        if entry.field == "name_ko" and entry.code not in terms:
            terms[entry.code] = {"name": entry.variant, "dict_type": entry.dict_type}
    return {"terms": terms, "count": len(terms)}


@app.get("/dictionary/version")
def dictionary_version() -> dict:
    """엔진이 만든 VERSION.json을 그대로 돌려주고, 낡았는지 함께 알린다.

    ⚠ 사전을 git merge로 갱신해 놓고 리로드를 부르지 않는 실수가 흔하다.
      인수인계 문서에 작성자가 두 번 당했다고 기록돼 있다. 그래서 물어보지
      않아도 낡았으면 낡았다고 말해준다.
    """
    payload = dict(version_payload())
    try:
        on_disk = load_dictionary_version(ONTOLOGY_DIR)
        payload["stale"] = (
            state.version is None or on_disk.content_hash != state.version.content_hash
        )
        if payload["stale"]:
            payload["disk_version"] = on_disk.version
    except VersionFileMissing:
        payload["stale"] = False
    return payload


@app.post("/admin/reload-dictionary")
def reload_dictionary() -> dict:
    """사전을 다시 읽는다.

    사전은 시작할 때 한 번만 메모리에 올라간다. git merge로 CSV가 바뀌어도
    이걸 부르기 전까지는 옛날 사전을 쓴다. 매핑률이 갑자기 이상하면
    이것부터 확인할 것.

    내용 해시로 판단하므로 같은 내용을 다시 내보냈을 때는 리로드하지 않는다.
    """
    before = version_payload().get("version")
    before_hash = version_payload().get("content_hash")

    _load()

    after = version_payload().get("version")
    after_hash = version_payload().get("content_hash")

    return {
        "reloaded": before_hash != after_hash,
        "from": before,
        "to": after,
    }
