"""DB에 쌓인 사람 판정을 사전 담당자에게 넘길 형식으로 뽑는다.

사전이 자라는 루프에서 끊겨 있던 고리다.

    사용자가 검증 화면에서 판정  →  review_items 테이블
                                        │
                                        │  ← 이 스크립트
                                        ▼
                              output/review_queue.csv
                                        │
                                        │  python pipeline/apply_review.py
                                        │  python ontology/import_review_log.py
                                        │  python ontology/export_ontology.py
                                        ▼
                                    표준 사전

왜 서버가 직접 사전을 고치지 않는가:
사전을 고치는 주체가 둘(팀은 git으로, 사용자는 검증 화면으로)이라,
서버가 CSV를 직접 쓰면 다음 git merge에 사용자 판정이 전부 사라진다.
그래서 판정은 DB에만 쌓고, 사전 반영은 담당자가 검토한 뒤 CLI로 한다.

사용법:

    python backend/tools/export_judgments.py
    python backend/tools/export_judgments.py --since 2026-08-10
    python backend/tools/export_judgments.py --dry-run

접속 정보는 환경변수로 준다(DB_HOST · DB_PORT · DB_NAME · DB_USER · DB_PASSWORD).
DB_PASSWORD가 없으면 실행할 때 물어본다. 비밀번호는 파일에 적지 않는다.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import datetime
from getpass import getpass
from pathlib import Path

import pymysql

# pipeline/run.py 가 정의한 검증 대기열 형식. 순서까지 같아야 apply_review가 읽는다.
QUEUE_COLUMNS = ["원본명", "출처파일", "후보 표준코드", "점수", "사람판정", "판정자"]

# apply_review.py 가 '기각'으로 인식하는 값. 이건 사전에 넣을 것이 없으므로 뽑지 않는다.
VERDICT_REJECT = "기각"

DEFAULT_OUTPUT = Path("output") / "review_queue.csv"


LOCAL_CONFIG = (
    Path(__file__).resolve().parents[1]
    / "src" / "main" / "resources" / "application-local.yml"
)


def password_from_local_config() -> str | None:
    """스프링이 쓰는 로컬 설정에서 비밀번호를 읽는다.

    이 파일은 .gitignore에 있어 저장소로 나가지 않는다. 스프링이 이미
    같은 파일을 읽고 있으므로, 여기서도 같은 값을 쓰면 접속 정보가 한 곳에만 남는다.

    yaml 라이브러리를 쓰지 않는 이유: 의존성을 하나 늘릴 만한 일이 아니고,
    여기서 필요한 것은 password 한 줄뿐이다.
    """
    if not LOCAL_CONFIG.exists():
        return None
    for line in LOCAL_CONFIG.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        if key.strip() == "password":
            value = value.strip().strip("'\"")
            return value or None
    return None


def connect(args) -> pymysql.connections.Connection:
    # 환경변수 → 로컬 설정 → 직접 입력 순서로 찾는다.
    password = os.environ.get("DB_PASSWORD")
    if password is None:
        password = password_from_local_config()
    if password is None:
        # 비밀번호를 인자로 받지 않는다. 명령 이력에 남기 때문이다.
        password = getpass("DB 비밀번호: ")

    return pymysql.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ.get("DB_USER", "root"),
        password=password,
        database=os.environ.get("DB_NAME", "awon"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def fetch_judgments(conn, since: str | None, include_exported: bool) -> list[dict]:
    """넘길 판정을 가져온다.

    기본은 '아직 안 넘긴 것'만이다. 같은 판정을 두 번 넘기면 사전에 중복 동의어가
    쌓이거나, 담당자가 이미 검토해 기각한 것이 다시 올라온다.
    """
    where = ["r.verdict IS NOT NULL", "r.verdict <> %s"]
    params: list = [VERDICT_REJECT]

    if not include_exported:
        where.append("r.exported_at IS NULL")
    if since:
        where.append("r.reviewed_at >= %s")
        params.append(since)

    sql = f"""
        SELECT r.id,
               r.raw,
               r.candidate_code,
               r.score,
               r.verdict,
               r.reviewed_by,
               r.reviewed_at,
               f.original_filename
          FROM review_items r
          JOIN files f ON f.id = r.file_id
         WHERE {' AND '.join(where)}
         ORDER BY r.reviewed_at ASC, r.id ASC
    """
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def to_queue_row(row: dict) -> dict:
    """DB 한 줄을 review_queue.csv 한 줄로 옮긴다.

    사람판정 칸에는 채택할 표준코드나 '승인'이 그대로 들어간다.
    apply_review.py가 두 형태를 모두 처리한다.
    """
    return {
        "원본명": row["raw"],
        "출처파일": row["original_filename"],
        "후보 표준코드": row["candidate_code"] or "",
        "점수": "" if row["score"] is None else row["score"],
        "사람판정": row["verdict"],
        "판정자": row["reviewed_by"] or "",
    }


def write_queue(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig — 담당자가 엑셀로 열어 검토하는 파일이라 BOM이 필요하다.
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=QUEUE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def mark_exported(conn, ids: list[int]) -> None:
    if not ids:
        return
    placeholders = ",".join(["%s"] * len(ids))
    with conn.cursor() as cur:
        cur.execute(
            f"UPDATE review_items SET exported_at = %s WHERE id IN ({placeholders})",
            [datetime.now(), *ids],
        )
    conn.commit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="DB의 사람 판정을 review_queue.csv 형식으로 뽑는다")
    parser.add_argument("--since", help="이 날짜 이후 판정만 (예: 2026-08-10)")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT),
                        help=f"출력 경로 (기본 {DEFAULT_OUTPUT})")
    parser.add_argument("--dry-run", action="store_true",
                        help="파일만 만들고 '넘김' 표시를 하지 않는다")
    parser.add_argument("--include-exported", action="store_true",
                        help="이미 넘긴 판정도 함께 뽑는다 (다시 만들 때)")
    args = parser.parse_args(argv)

    try:
        conn = connect(args)
    except pymysql.err.OperationalError as e:
        code = e.args[0] if e.args else 0
        if code == 1045:
            print("DB 접속이 거부됐습니다. 사용자 이름과 비밀번호를 확인해 주세요.", file=sys.stderr)
            print("  DB_USER / DB_PASSWORD 환경변수로 줄 수 있습니다.", file=sys.stderr)
        elif code == 1049:
            print(f"데이터베이스 '{os.environ.get('DB_NAME', 'awon')}'가 없습니다.", file=sys.stderr)
        elif code == 2003:
            print("MySQL 서버에 연결하지 못했습니다. 서버가 켜져 있는지 확인해 주세요.", file=sys.stderr)
        else:
            print(f"DB 접속 실패: {e}", file=sys.stderr)
        return 1

    try:
        rows = fetch_judgments(conn, args.since, args.include_exported)

        if not rows:
            print("넘길 판정이 없습니다.")
            return 0

        output = Path(args.output)
        write_queue([to_queue_row(r) for r in rows], output)

        print(f"판정 {len(rows)}건 → {output}")
        for r in rows:
            print(f"  {r['raw']!r:32} → {r['verdict']:10} "
                  f"({r['reviewed_by'] or '판정자 미상'}, 출처: {r['original_filename']})")

        if args.dry_run:
            print("\n--dry-run 이므로 '넘김' 표시를 하지 않았습니다. "
                  "다시 실행하면 같은 판정이 또 나옵니다.")
        else:
            mark_exported(conn, [r["id"] for r in rows])
            print(f"\n{len(rows)}건에 넘김 표시를 했습니다. 다음 실행에는 나오지 않습니다.")

        print("\n다음 단계 — 사전 담당자가 근거를 확인한 뒤:")
        print(f"  python pipeline/apply_review.py {output}")
        print("  python ontology/import_review_log.py     ← 빠뜨리면 다음 export에서 사라진다")
        print("  python ontology/export_ontology.py")
        print("  python -m pytest && python run.py ./data/samples/   ← 회귀 확인")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
