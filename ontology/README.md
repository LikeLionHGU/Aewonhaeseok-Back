# ontology/ — 표준 용어 사전

사전은 **두 형태로 존재한다.** 이 구분을 모르면 작업이 조용히 유실된다.

```
ontology/
├── measurement_terms.csv     ← 엔진이 읽는 평면 사전 (생성물, 직접 수정 금지)
├── metadata_terms.csv        ← 엔진이 읽는 평면 사전 (생성물, 직접 수정 금지)
├── export_ontology.py        원본 → 평면 (엔진 형식으로 투영)
├── import_review_log.py      리뷰 승인분 → 원본 (왕복을 닫는다)
├── review_log.csv            apply_review.py가 남기는 반영 이력 (자동 생성)
└── source/                   ★ 사전의 원본 ★
    ├── measurement_terms.csv   측정항목 76행
    ├── metadata_terms.csv      관측 메타 30행
    ├── term_synonyms.csv       동의어 333행 — 1행 = 1표기 × 1출처
    ├── term_sources.csv        출처 19곳 + 신뢰도
    ├── schema.sql              PostgreSQL 스키마 (최종 저장소)
    ├── seed.sql                시드 INSERT
    ├── build_dictionary.py     원본 CSV 생성기
    ├── check_dictionary.py     원본 무결성 점검 (pytest 대상 아님 — 독립 실행)
    └── README.md               사전 내용·근거·초안 대비 정정 내역
```

## 왜 두 형태인가

`source/`는 동의어 하나가 한 행이고 **출처와 수집일이 각각 붙는다.** 근거를 남기려면 이 형태여야 한다.
같은 `수소이온농도`라도 전북·제주·안양·당진이 각각 쓴다는 사실이 4개 행으로 남는다.

`pipeline/mapper.py`는 한 항목이 한 행이고 동의어가 파이프로 이어 붙은 형태를 읽는다
(`code / name_ko / name_en / abbr / synonyms`). 이 다섯 컬럼이 매칭에 쓰이는 전부다.

그래서 `export_ontology.py`가 원본을 평면으로 투영한다. **평면은 생성물이다.**

## 작업 흐름

```
python run.py ./data/samples/
      ↓  output/review_queue.csv  (needs_review + unmapped)
사람이 '사람판정' 칸을 채운다 — 표준코드 직접 기입 또는 '승인'/'기각'
      ↓
python pipeline/apply_review.py output/review_queue.csv
      ↓  평면 사전의 synonyms에 반영 + ontology/review_log.csv 기록
python ontology/import_review_log.py        ← 빠뜨리면 다음 export에서 사라진다
      ↓  source/term_synonyms.csv 에 출처·수집일과 함께 편입
python ontology/export_ontology.py
      ↓  평면 재생성. 승인분이 그대로 살아남는다
```

`import_review_log.py`를 건너뛰고 `export_ontology.py`를 돌리면 사람이 승인한 동의어가
평면에서 지워진다. 원본에 없기 때문이다. **순서를 지킬 것.**

## export_ontology.py가 하는 정리

원본을 그대로 평면에 옮기면 엔진이 로딩에 실패한다. 두 가지를 걸러 준다.

**1. rejected 항목·동의어 제외** — 근거가 확인되지 않은 것은 매칭되면 안 된다.

**2. 본체가 이미 색인된 동의어 생략** — 엔진은 괄호 안 내용을 약어 후보로 **따로** 색인한다.
그래서 `총인(total phosphorus)`은 본체 `총인`(표준명과 동일) 외에 `total`·`phosphorus`를
약어로 색인하는데, `total`은 `총질소(total nitrogen)`와 충돌한다. `total`은 약어가 아니라 일반 단어다.
본체만으로 이미 매칭되므로 이런 동의어는 평면에서 뺀다. 근거는 `source/term_synonyms.csv`에 그대로 남는다.

진짜 약어는 `abbr` 컬럼에 있어야지 괄호부에서 우연히 주워지면 안 된다.

`export_ontology.py`는 마지막에 엔진의 `load_lexicon()`을 직접 호출해 표기 충돌이 없는지 확인한다.
충돌이 있으면 종료 코드 1로 실패하므로, 깨진 사전이 배포되지 않는다.

```bash
python3 ontology/export_ontology.py                    # 전체
python3 ontology/export_ontology.py --exclude-inferred # 미검증(AI 추정) 동의어 제외
```

## 사전을 고칠 때

**평면 CSV를 직접 고치지 마라.** `source/`를 고치고 `export_ontology.py`를 다시 돌린다.

- 새 항목/근거 수정 → `source/build_dictionary.py`를 고치고 실행
- 새 동의어 한 건 → `source/term_synonyms.csv`에 행 추가 (출처와 수집일 필수)
- 무결성 확인 → `python3 ontology/source/check_dictionary.py`

괄호를 떼면 다른 항목과 같아지는 표기는 사전에 넣으면 안 된다. 이미 다섯 건을 그 이유로 폐기했고
(`질소(총)`, `인(총)`, `유분(광유)`, `유분(동식물유지)`, `Cr(VI)`), 폐기 사유는
`source/term_synonyms.csv`에 `review_status=rejected`로 남아 있다.

## 최종 저장소는 PostgreSQL

CSV는 부트스트랩이다. `source/schema.sql` + `source/seed.sql`로 DB에 올리면
동의어별 출처·수집일, 매칭 함수(`wq_match_column`), 미해결 컬럼 큐(`unresolved_columns`)가
전부 DB 안에서 돈다. 그 뒤로는 DB가 원본이고 `source/*.csv`는 그 export가 된다.

```bash
psql -d <db> -f ontology/source/schema.sql
psql -d <db> -f ontology/source/seed.sql
```

사전의 내용·근거·초안 대비 정정 내역은 `source/`와 함께 있는 상위 README를 참고할 것.
