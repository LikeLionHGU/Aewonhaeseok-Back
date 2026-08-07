"""전체 실행 진입점.

    python run.py ./data/samples/

- ./ontology/ 의 두 표준 사전을 로딩
- 대상 디렉토리의 xlsx/csv를 전부 매핑
- output/mapped/{원본파일명}_mapped.csv, output/report.json, output/review_queue.csv 생성
- 파일별 자동 매핑률/확인 필요율/실패율 표 출력
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline import config
from pipeline.mapper import (
    STATUS_NEEDS_REVIEW,
    STATUS_UNMAPPED,
    FileMapping,
    Lexicon,
    load_lexicon,
    map_file,
    output_column_name,
)

_DATA_SUFFIXES = {".csv", ".xlsx", ".xlsm", ".xls"}

REVIEW_QUEUE_COLUMNS = ["원본명", "출처파일", "후보 표준코드", "점수", "사람판정", "판정자"]


def find_data_files(samples_dir: Path) -> list[Path]:
    files = [
        p for p in sorted(samples_dir.rglob("*"))
        if p.is_file()
        and p.suffix.lower() in _DATA_SUFFIXES
        and not p.name.startswith(("~$", "."))
    ]
    return files


def build_report(mappings: list[FileMapping]) -> dict:
    def overall_summary() -> dict:
        all_results = [r for m in mappings for r in m.results]
        total = len(all_results)
        n_auto = sum(1 for r in all_results if r.adopted)
        n_review = sum(1 for r in all_results if r.status == STATUS_NEEDS_REVIEW)
        n_unmapped = sum(1 for r in all_results if r.status == STATUS_UNMAPPED)
        pct = (lambda n: round(100.0 * n / total, 1) if total else 0.0)
        return {
            "파일 수": len(mappings),
            "전체 컬럼 수": total,
            "자동 매핑률": pct(n_auto),
            "확인 필요율": pct(n_review),
            "실패율": pct(n_unmapped),
        }

    files = []
    for m in mappings:
        columns = []
        for r in m.results:
            columns.append({
                "원본명": r.raw,
                "정규화명": r.norm.display,
                "결과": r.status,
                "판정경로": r.via,
                "표준코드": r.code if r.adopted else r.candidate_code,
                "지점명": r.site,
                "출력 컬럼명": output_column_name(r),
                "매칭 문자열": r.matched_variant,
                "점수": r.score,
                "사전 종류": r.dict_type,
            })
        files.append({
            "파일": m.path.name,
            "헤더 행": m.header_row,
            "columns": columns,
            "summary": m.summary(),
        })

    return {"summary": overall_summary(), "files": files}


def build_review_queue(mappings: list[FileMapping]) -> pd.DataFrame:
    """needs_review + unmapped만 모은 확인 대기열.

    사람판정 칸에는 채택할 표준코드(후보 승인 시 '승인')를, 기각 시 '기각'을 적는다.
    채운 뒤 apply_review.py로 사전 synonyms에 반영한다.
    """
    rows = []
    for m in mappings:
        for r in m.results:
            if r.status == STATUS_NEEDS_REVIEW:
                rows.append({
                    "원본명": r.raw, "출처파일": m.path.name,
                    "후보 표준코드": r.candidate_code, "점수": r.score,
                    "사람판정": "", "판정자": "",
                })
            elif r.status == STATUS_UNMAPPED:
                # 임계값 미만의 후보는 노이즈이므로 제안하지 않는다
                rows.append({
                    "원본명": r.raw, "출처파일": m.path.name,
                    "후보 표준코드": "", "점수": "",
                    "사람판정": "", "판정자": "",
                })
    return pd.DataFrame(rows, columns=REVIEW_QUEUE_COLUMNS)


def _display_width(text: str) -> int:
    """터미널 표시 폭. 한글 등 전각 문자는 두 칸을 차지한다."""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def _pad(text: str, width: int, align: str) -> str:
    space = " " * max(0, width - _display_width(text))
    return text + space if align == "left" else space + text


def _fit(text: str, width: int) -> str:
    """열 폭을 넘는 문자열은 잘라내고 말줄임표를 붙인다."""
    if _display_width(text) <= width:
        return text
    kept = ""
    for ch in text:
        if _display_width(kept + ch) > width - 2:
            break
        kept += ch
    return kept + ".."


_NAME_COLUMN_MAX = 44
_COLUMNS = (
    ("컬럼수", 6, "right"),
    ("자동매핑률", 10, "right"),
    ("확인필요율", 10, "right"),
    ("실패율", 8, "right"),
)


def print_summary_table(report: dict) -> None:
    rows = [(f["파일"], f["summary"]) for f in report["files"]]
    name_width = min(
        _NAME_COLUMN_MAX,
        max(_display_width(name) for name, _ in rows + [("파일", None), ("전체", None)]),
    )
    widths = (name_width, *(w for _, w, _ in _COLUMNS))
    aligns = ("left", *(a for _, _, a in _COLUMNS))

    def line(cells: tuple[str, ...]) -> str:
        return "  ".join(_pad(c, w, a) for c, w, a in zip(cells, widths, aligns))

    def data_line(name: str, s: dict) -> str:
        return line((
            _fit(name, name_width),
            str(s["전체 컬럼 수"]),
            f"{s['자동 매핑률']:.1f}%",
            f"{s['확인 필요율']:.1f}%",
            f"{s['실패율']:.1f}%",
        ))

    header = line(tuple(h for h, _, _ in (("파일", 0, ""), *_COLUMNS)))
    rule = "-" * _display_width(header)

    print()
    print(header)
    print(rule)
    for name, s in rows:
        print(data_line(name, s))
    print(rule)
    print(data_line("전체", report["summary"]))


def run(samples_dir: Path, ontology_dir: Path, output_dir: Path) -> dict:
    lexicon: Lexicon = load_lexicon(
        ontology_dir / config.MEASUREMENT_DICT_FILENAME,
        ontology_dir / config.METADATA_DICT_FILENAME,
    )

    files = find_data_files(samples_dir)
    if not files:
        raise SystemExit(f"데이터 파일이 없습니다: {samples_dir}")

    mapped_dir = output_dir / "mapped"
    mapped_dir.mkdir(parents=True, exist_ok=True)

    mappings: list[FileMapping] = []
    for path in files:
        m = map_file(path, lexicon)
        mappings.append(m)
        out_path = mapped_dir / f"{path.stem}_mapped.csv"
        m.mapped_df.to_csv(out_path, index=False, encoding="utf-8-sig")

    report = build_report(mappings)
    report_path = output_dir / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    queue = build_review_queue(mappings)
    queue.to_csv(output_dir / "review_queue.csv", index=False, encoding="utf-8-sig")

    print_summary_table(report)
    print(f"\n출력: {mapped_dir}/, {report_path}, {output_dir / 'review_queue.csv'}")
    return report


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description="수질 데이터 컬럼 매핑 파이프라인")
    parser.add_argument("samples_dir", help="기관별 데이터 파일 디렉토리 (예: ./data/samples/)")
    parser.add_argument("--ontology", default=config.ONTOLOGY_DIR, help="표준 사전 디렉토리")
    parser.add_argument("--output", default=config.OUTPUT_DIR, help="출력 디렉토리")
    args = parser.parse_args(argv)

    return run(Path(args.samples_dir), Path(args.ontology), Path(args.output))


if __name__ == "__main__":
    main()
