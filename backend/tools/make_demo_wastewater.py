"""폐수 데모 데이터 생성.

⚠ 이 데이터는 실측치가 아니다. 구조는 법정 서식을 따르지만 값은 만든 것이다.
   발표·심사 자료에 쓸 때는 반드시 '데모 데이터'라고 밝힐 것.

왜 만드는가:
타깃이 폐수측정 업체로 확정됐는데 폐수 실데이터가 한 벌도 없다. 사전에 새로 넣은
폐수 용어 28건이 실제로 몇 %를 잡는지 모르고, 측정값 테이블(B5)도 추측으로
설계하게 된다. 실데이터를 구하기 전까지 그 자리를 메운다.

근거:
컬럼 이름을 지어내지 않고 사전(ontology/)에 이미 등록된 표기를 그대로 쓴다.
그 표기들의 출처는 아래 셋이며, 사전의 legal_basis 칸에 기록돼 있다.

  · 물환경보전법 시행규칙 별지 제18호서식 (폐수배출시설 및 수질오염방지시설 운영일지)
  · 물환경보전법 시행규칙 별지 제20호서식 (폐수배출시설 운영일지)
  · 수질원격감시체계(TMS) 관제센터 운영 등에 관한 규정 (환경부고시)

즉 "실제 성적서가 이렇게 생겼을 것"이라는 추측이 아니라,
"법이 이 칸들을 적으라고 정해두었다"는 근거 위에서 만든 구조다.

    python backend/tools/make_demo_wastewater.py
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO_ROOT / "data" / "demo_wastewater"

# 재현 가능하게 고정한다. 돌릴 때마다 숫자가 바뀌면 회귀 확인이 안 된다.
SEED = 20260811

# ─────────────────────────────────────────────────────────────────
# 가상의 사업장. 이름에 '데모'를 넣어 실제 사업장과 혼동되지 않게 한다.
# ─────────────────────────────────────────────────────────────────
SITES = [
    {"name": "데모금속(주)", "outlets": ["1배출구", "2배출구"], "method": "물리화학적처리"},
    {"name": "데모섬유공업(주)", "outlets": ["1배출구"], "method": "생물학적처리"},
    {"name": "데모화학(주)", "outlets": ["1배출구", "2배출구", "3배출구"], "method": "물리화학적처리"},
]

# ─────────────────────────────────────────────────────────────────
# 측정항목 — (컬럼명, 단위, 정상범위, 배출허용기준)
# 기준치는 물환경보전법 시행규칙 별표 13 '청정지역' 수준을 참고한 예시값이다.
# B6에서 법령 원문으로 정식 테이블을 만들기 전까지의 자리표시자다.
# ─────────────────────────────────────────────────────────────────
ITEMS = [
    ("수소이온농도", "",     (6.5, 8.5),   None),
    ("생물화학적산소요구량", "㎎/L", (2.0, 28.0),  30.0),
    ("화학적산소요구량", "㎎/L", (5.0, 38.0),  40.0),
    ("부유물질", "㎎/L",   (3.0, 28.0),  30.0),
    ("총질소", "㎎/L",     (5.0, 55.0),  60.0),
    ("총인", "㎎/L",       (0.3, 7.0),   8.0),
    ("총유기탄소", "㎎/L",  (2.0, 23.0),  25.0),
]

# ─────────────────────────────────────────────────────────────────
# 운영일지 (별지 제18호서식) — 수량·슬러지 축
# 사전 코드 WQ-077~087, MD-035·039·040·041·066·067 에 대응한다.
# ─────────────────────────────────────────────────────────────────
OPERATION_COLUMNS = [
    "사업장 명칭", "방류구", "처리방법",
    "분석일", "폐수배출시설 가동(조업)시간대", "수질오염방지시설 가동시간대",
    "용수사용량(㎥/일)", "폐수발생량(㎥/일)", "폐수배출량(㎥/일)",
    "냉각수량(㎥/일)", "재사용량(㎥/일)", "생활용수량(㎥/일)",
    "슬러지 발생량(㎥)", "슬러지 처리량(㎥)", "슬러지 보관량(㎥)", "함수율(%)",
    "측정대행업소명", "분석자명",
]

# ─────────────────────────────────────────────────────────────────
# TMS 실시간 측정 (수질원격감시체계 고시)
# 사전 코드 MD-033·046·050·052·053·054·055·072·073·074, WQ-075 에 대응한다.
# ─────────────────────────────────────────────────────────────────
TMS_COLUMNS = [
    "사업장 명칭", "방류구", "측정일시", "측정방법",
    "수소이온농도", "총유기탄소(㎎/L)", "부유물질(㎎/L)",
    "총질소(㎎/L)", "총인(㎎/L)", "유량(㎥/s)",
    "24시간 평균치", "일일 평균 농도", "일일 배출량",
    "초과오염물질", "초과농도", "초과량", "초과시간",
    "배출허용기준", "방류수수질기준",
]


def rnd(rng: random.Random, low: float, high: float, digits: int = 1) -> float:
    return round(rng.uniform(low, high), digits)


def write_csv(path: Path, columns: list[str], rows: list[list], encoding: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding=encoding, newline="") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)


def build_report(rng: random.Random, days: int) -> tuple[list[str], list[list]]:
    """측정 성적서 — 측정값 옆에 배출허용기준이 함께 오는 가로형 구조.

    ★ 이 형태가 B5·B6 설계의 핵심이다.
      같은 항목이 '측정값' 칸과 '기준' 칸 두 번 나온다. 둘을 구분하지 못하면
      기준값이 측정값으로 적재돼 통계가 통째로 틀어진다.
      홀드아웃 판정 가이드가 '기준값 컬럼이 측정값으로 매핑되면 오답'이라고
      규정해 둔 상황이 실제로 여기서 발생한다.
    """
    columns = ["사업장 명칭", "방류구", "시료채취일", "시료구분", "측정대행업소명"]
    for name, unit, _, limit in ITEMS:
        columns.append(f"{name}({unit})" if unit else name)
        if limit is not None:
            columns.append(f"{name} 배출허용기준")

    rows: list[list] = []
    start = date(2026, 3, 2)
    for site in SITES:
        for outlet in site["outlets"]:
            for d in range(days):
                sampled = start + timedelta(days=d * 7)
                for kind in ("원폐수", "방류수"):
                    row = [site["name"], outlet, sampled.isoformat(), kind, "데모환경분석(주)"]
                    for name, unit, (lo, hi), limit in ITEMS:
                        if kind == "원폐수":
                            # 처리 전이라 농도가 높다. pH는 그대로 둔다.
                            value = rnd(rng, lo, hi) if name == "수소이온농도" \
                                else rnd(rng, lo * 3, hi * 4)
                        else:
                            value = rnd(rng, lo, hi)
                            # 방류수에서 가끔 기준을 넘긴다 — 초과 판정 로직을 시험하기 위함
                            if limit is not None and rng.random() < 0.06:
                                value = round(limit * rng.uniform(1.05, 1.4), 1)
                        row.append(value)
                        if limit is not None:
                            row.append(limit)
                    rows.append(row)
    return columns, rows


def build_operation(rng: random.Random, days: int) -> tuple[list[str], list[list]]:
    """운영일지 — 별지 제18호서식의 수량·슬러지 칸."""
    rows: list[list] = []
    start = date(2026, 3, 2)
    for site in SITES:
        for outlet in site["outlets"]:
            for d in range(days * 2):
                day = start + timedelta(days=d * 3)
                water = rnd(rng, 120, 480, 0)
                waste = round(water * rng.uniform(0.55, 0.8), 0)
                discharged = round(waste * rng.uniform(0.7, 0.95), 0)
                rows.append([
                    site["name"], outlet, site["method"],
                    day.isoformat(), "09:00~18:00", "09:00~18:00",
                    water, waste, discharged,
                    round(water * rng.uniform(0.05, 0.2), 0),
                    round(waste * rng.uniform(0.02, 0.12), 0),
                    round(water * rng.uniform(0.02, 0.08), 0),
                    rnd(rng, 0.5, 4.0), rnd(rng, 0.4, 3.6), rnd(rng, 0.2, 2.0),
                    rnd(rng, 78.0, 88.0),
                    "데모환경분석(주)", "김분석",
                ])
    return OPERATION_COLUMNS, rows


def build_tms(rng: random.Random, days: int) -> tuple[list[str], list[list]]:
    """TMS 실시간 측정 — 고시가 저장하도록 규정한 항목들."""
    rows: list[list] = []
    start = date(2026, 3, 2)
    for site in SITES:
        for outlet in site["outlets"]:
            for d in range(days * 3):
                stamp = f"{(start + timedelta(days=d)).isoformat()} {rng.choice(['00', '06', '12', '18'])}:00"
                toc = rnd(rng, 2.0, 24.0)
                over = toc > 25.0
                rows.append([
                    site["name"], outlet, stamp, "자동측정기기",
                    rnd(rng, 6.5, 8.5), toc, rnd(rng, 3.0, 28.0),
                    rnd(rng, 5.0, 55.0), rnd(rng, 0.3, 7.0), rnd(rng, 0.001, 0.05, 3),
                    rnd(rng, 2.0, 22.0), rnd(rng, 2.0, 22.0), rnd(rng, 40, 400, 0),
                    "총유기탄소" if over else "",
                    toc if over else "",
                    rnd(rng, 0.1, 3.0) if over else "",
                    rng.choice([1, 2, 3]) if over else "",
                    25.0, 20.0,
                ])
    return TMS_COLUMNS, rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="폐수 데모 데이터 생성 (실측치 아님)")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--weeks", type=int, default=8, help="기간 (기본 8주)")
    args = parser.parse_args(argv)

    rng = random.Random(SEED)
    out = Path(args.output)

    builders = [
        ("데모_폐수배출사업장_측정성적서.csv", build_report, "utf-8-sig"),
        # 운영일지는 cp949로 쓴다. 공공기관 파일이 cp949가 태반이라
        # 인코딩 폴백 경로가 실제로 쓰이는지 여기서도 확인된다.
        ("데모_폐수배출시설_운영일지.csv", build_operation, "cp949"),
        ("데모_수질원격감시_TMS.csv", build_tms, "utf-8-sig"),
    ]

    for filename, builder, encoding in builders:
        columns, rows = builder(rng, args.weeks)
        path = out / filename
        write_csv(path, columns, rows, encoding)
        print(f"  {len(rows):5,}행 × {len(columns):2}열  [{encoding:9}]  {path.name}")

    readme = out / "README.md"
    readme.write_text(
        "# 폐수 데모 데이터\n\n"
        "**⚠ 실측치가 아니다.** 구조는 법정 서식을 따르지만 값은 생성한 것이다.\n"
        "발표·심사 자료에 쓸 때는 반드시 '데모 데이터'라고 밝힐 것.\n\n"
        "## 구조의 근거\n\n"
        "컬럼 이름을 지어내지 않고 표준 사전(`ontology/`)에 등록된 표기를 그대로 썼다.\n"
        "그 표기들의 출처는 사전의 `legal_basis` 칸에 기록돼 있다.\n\n"
        "| 파일 | 근거 |\n|---|---|\n"
        "| 측정성적서 | 물환경보전법 시행규칙 별표 13 (배출허용기준 항목) |\n"
        "| 운영일지 | 같은 규칙 별지 제18호서식 · 제20호서식 |\n"
        "| TMS | 수질원격감시체계 관제센터 운영 등에 관한 규정 (환경부고시) |\n\n"
        "## 일부러 넣어 둔 것\n\n"
        "- **측정값 옆의 기준치 컬럼** — 기준값이 측정값으로 잘못 매핑되면 오답이다.\n"
        "  이 함정이 실제로 걸러지는지 확인하기 위한 것이다.\n"
        "- **원폐수 / 방류수 구분** — 같은 항목이라도 처리 전후로 뜻이 정반대다.\n"
        "- **기준 초과 사례** — 방류수에서 약 6% 확률로 기준을 넘긴다.\n"
        "- **cp949 인코딩 파일** — 공공기관 파일 대부분이 cp949다.\n\n"
        "재현: `python backend/tools/make_demo_wastewater.py` (시드 고정)\n",
        encoding="utf-8")

    print(f"\n출력: {out}")
    print("⚠ 실측치가 아니다. 발표에 쓸 때 '데모 데이터'임을 밝힐 것.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
