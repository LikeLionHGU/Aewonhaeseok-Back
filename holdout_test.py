"""홀드아웃 테스트 — 사전이 처음 보는 파일에서 매핑률을 재고, 학습 전후를 비교한다.

  1차 (사전이 처음 보는 상태):
      python3 holdout_test.py ./data/holdout/

  사람이 output_holdout/review_queue.csv 의 '사람판정'을 채운 뒤:
      python3 pipeline/apply_review.py output_holdout/review_queue.csv
      python3 ontology/import_review_log.py
      python3 ontology/export_ontology.py

  2차 (사전이 학습한 뒤):
      python3 holdout_test.py ./data/holdout/ --round 2

  마지막에 1차 대비 2차 상승폭을 표로 출력한다. 이 두 숫자가 발표의 핵심 증거다.

왜 이걸 따로 만드는가:
  data/samples/ 6개 파일의 98.2%는 사전을 만들면서 함께 본 파일이라 in-sample 수치다.
  성능을 주장하려면 사전이 한 번도 보지 못한 파일의 첫 실행 숫자를 써야 한다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from pipeline import config  # noqa: E402
from pipeline.run import run as run_pipeline  # noqa: E402

HISTORY = ROOT / "output_holdout" / "rounds.json"


def load_history() -> dict:
    if HISTORY.exists():
        return json.loads(HISTORY.read_text(encoding="utf-8"))
    return {}


def save_round(n: int, report: dict) -> dict:
    hist = load_history()
    hist[str(n)] = {
        "summary": report["summary"],
        "files": {f["파일"]: f["summary"] for f in report["files"]},
    }
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    HISTORY.write_text(json.dumps(hist, ensure_ascii=False, indent=2), encoding="utf-8")
    return hist


def print_growth(hist: dict) -> None:
    if "1" not in hist or "2" not in hist:
        return
    a, b = hist["1"]["summary"], hist["2"]["summary"]
    print("\n" + "=" * 62)
    print("사전 학습 전후 비교 — 발표 핵심 증거")
    print("=" * 62)
    print(f"{'지표':<14}{'1차':>10}{'2차':>10}{'변화':>12}")
    print("-" * 62)
    for key in ("자동 매핑률", "확인 필요율", "실패율"):
        d = b[key] - a[key]
        print(f"{key:<14}{a[key]:>9.1f}%{b[key]:>9.1f}%{d:>+11.1f}%p")
    print("-" * 62)
    print(f"전체 컬럼 수: {a['전체 컬럼 수']}개 (파일 {a['파일 수']}개)")
    print("\n파일별 자동 매핑률")
    for name, s1 in hist["1"]["files"].items():
        s2 = hist["2"]["files"].get(name)
        if s2:
            print(f"  {name[:34]:<36}{s1['자동 매핑률']:>6.1f}% → {s2['자동 매핑률']:>6.1f}%")


def main() -> None:
    ap = argparse.ArgumentParser(description="홀드아웃 테스트")
    ap.add_argument("holdout_dir", help="사전이 본 적 없는 데이터 디렉토리")
    ap.add_argument("--round", type=int, default=1, choices=(1, 2),
                    help="1=학습 전 첫 실행, 2=사람 판정 반영 후 재실행")
    ap.add_argument("--ontology", default=config.ONTOLOGY_DIR)
    ap.add_argument("--output", default="output_holdout")
    args = ap.parse_args()

    d = Path(args.holdout_dir)
    if not d.is_dir():
        raise SystemExit(
            f"디렉토리가 없습니다: {d}\n"
            f"  mkdir -p {d} 로 만들고 내려받은 CSV/XLSX를 넣으세요."
        )

    print(f"\n▶ 홀드아웃 {args.round}차 실행 — {d}")
    report = run_pipeline(d, Path(args.ontology), Path(args.output))
    hist = save_round(args.round, report)

    s = report["summary"]
    if args.round == 1:
        print("\n" + "=" * 62)
        print("1차 결과 — 사전이 처음 보는 데이터")
        print(f"  자동 매핑률 {s['자동 매핑률']}%  확인 필요 {s['확인 필요율']}%  실패 {s['실패율']}%")
        print("=" * 62)
        print("다음 단계:")
        print(f"  1) {args.output}/review_queue.csv 의 '사람판정'·'판정자'를 채운다")
        print(f"  2) python3 pipeline/apply_review.py {args.output}/review_queue.csv")
        print( "  3) python3 ontology/import_review_log.py   ← 빠뜨리면 다음 export에서 사라진다")
        print( "  4) python3 ontology/export_ontology.py")
        print(f"  5) python3 holdout_test.py {d} --round 2")
    else:
        print_growth(hist)

    print(f"\n기록: {HISTORY}")


if __name__ == "__main__":
    main()
