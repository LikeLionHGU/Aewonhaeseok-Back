"""사전 버전 — 결과 화면의 `사전 버전` 표시와 리로드 판단에 쓴다.

버전 파일 `ontology/VERSION.json`은 `export_ontology.py`가 평면 사전을 만들 때 함께 생성한다.
사람이 손으로 쓰지 않는다. 사전이 바뀌면 자동으로 바뀐다.

백엔드 사용법:

    from pipeline.version import load_dictionary_version

    v = load_dictionary_version()          # ontology/ 기본 경로
    v.version                              # 'dict-2026-08-08'  ← 화면에 그대로 표시
    v.content_hash                         # 'a1b2c3d4...'      ← 바뀌면 리로드
    v.as_dict()                            # GET /dictionary/version 응답 그대로

왜 두 개인가:
  version      사람이 읽는 이름. git 태그와 같은 규칙(dict-YYYY-MM-DD)이라 이력 추적이 된다.
  content_hash 같은 날 두 번 고쳐도 달라진다. 리로드가 필요한지는 이걸로 판단한다.
               날짜만 보면 같은 날의 두 번째 변경을 놓친다.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import config

VERSION_FILENAME = "VERSION.json"


@dataclass(frozen=True)
class DictionaryVersion:
    version: str            # dict-YYYY-MM-DD — 화면 표시용
    content_hash: str       # 평면 사전 2개의 내용 해시 — 변경 감지용
    generated_at: str       # ISO 날짜
    measurement_terms: int
    metadata_terms: int
    synonyms: int
    verified_terms: int
    excluded_inferred: bool = False   # --exclude-inferred 로 만든 사전인가
    note: str = ""
    extra: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        d = {
            "version": self.version,
            "content_hash": self.content_hash,
            "generated_at": self.generated_at,
            "counts": {
                "measurement_terms": self.measurement_terms,
                "metadata_terms": self.metadata_terms,
                "synonyms": self.synonyms,
                "verified_terms": self.verified_terms,
            },
            "excluded_inferred": self.excluded_inferred,
        }
        if self.note:
            d["note"] = self.note
        return d


class VersionFileMissing(FileNotFoundError):
    """VERSION.json이 없다. export_ontology.py를 돌리지 않았다는 뜻이다."""


def compute_content_hash(measurement_path: Path, metadata_path: Path) -> str:
    """평면 사전 2개의 내용 해시. 파일 시각이 아니라 내용만 본다.

    같은 내용을 다시 export해도 해시가 바뀌지 않아야 백엔드가 불필요하게 리로드하지 않는다.
    """
    h = hashlib.sha256()
    for p in (measurement_path, metadata_path):
        h.update(Path(p).read_bytes())
    return h.hexdigest()[:16]


def build_version(
    measurement_path: Path,
    metadata_path: Path,
    *,
    measurement_terms: int,
    metadata_terms: int,
    synonyms: int,
    verified_terms: int,
    excluded_inferred: bool = False,
    note: str = "",
    today: date | None = None,
) -> DictionaryVersion:
    d = today or date.today()
    return DictionaryVersion(
        version=f"dict-{d.isoformat()}",
        content_hash=compute_content_hash(measurement_path, metadata_path),
        generated_at=d.isoformat(),
        measurement_terms=measurement_terms,
        metadata_terms=metadata_terms,
        synonyms=synonyms,
        verified_terms=verified_terms,
        excluded_inferred=excluded_inferred,
        note=note,
    )


def write_version(path: Path, v: DictionaryVersion) -> None:
    Path(path).write_text(
        json.dumps(v.as_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def load_dictionary_version(ontology_dir: Path | str = config.ONTOLOGY_DIR) -> DictionaryVersion:
    """VERSION.json을 읽는다. 없으면 VersionFileMissing.

    백엔드는 서버 시작 시 이걸 읽어 두고, 결과에 함께 실어 보낸다.
    """
    p = Path(ontology_dir) / VERSION_FILENAME
    if not p.exists():
        raise VersionFileMissing(
            f"{p} 가 없습니다. 사전을 내보내면 함께 생깁니다:\n"
            f"  python3 ontology/export_ontology.py"
        )
    raw = json.loads(p.read_text(encoding="utf-8"))
    c = raw.get("counts", {})
    return DictionaryVersion(
        version=raw["version"],
        content_hash=raw["content_hash"],
        generated_at=raw["generated_at"],
        measurement_terms=c.get("measurement_terms", 0),
        metadata_terms=c.get("metadata_terms", 0),
        synonyms=c.get("synonyms", 0),
        verified_terms=c.get("verified_terms", 0),
        excluded_inferred=raw.get("excluded_inferred", False),
        note=raw.get("note", ""),
    )


def is_stale(loaded: DictionaryVersion, ontology_dir: Path | str = config.ONTOLOGY_DIR) -> bool:
    """메모리에 올려둔 사전이 낡았는가.

    백엔드가 주기적으로 호출하거나 리로드 엔드포인트에서 확인한다.
    True면 load_lexicon()을 다시 부른다.
    """
    try:
        return load_dictionary_version(ontology_dir).content_hash != loaded.content_hash
    except VersionFileMissing:
        return False
