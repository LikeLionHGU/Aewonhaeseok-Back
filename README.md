# 수질 데이터 컬럼 매핑 엔진

기관마다 다른 컬럼명을 표준 코드로 바꿔준다.

```
총질소 / T-N / itemTn / 총소질소   →   WQ-005
```

---

## 1. 설치와 실행

```bash
python3 -m pip install -r requirements.txt
python3 run.py ./data/samples/
```

결과는 `output/`에 3개 생긴다.

| 파일 | 내용 |
|---|---|
| `output/mapped/*.csv` | 컬럼명이 표준코드로 바뀐 데이터 |
| `output/report.json` | 컬럼별 판정 결과와 근거 |
| `output/review_queue.csv` | 사람이 봐야 할 것만 모음 |

---

## 2. 백엔드가 쓸 함수 4개

```python
from pipeline.mapper import load_lexicon, map_file, map_column
from pipeline.apply_review import apply_review
```

### ① 사전 읽기 — 서버 시작할 때 1번

```python
lexicon = load_lexicon("ontology/measurement_terms.csv",
                       "ontology/metadata_terms.csv")
```

### ② 파일 하나 매핑 — 사용자가 업로드했을 때

```python
result = map_file("업로드된파일.xlsx", lexicon)

result.mapped_df    # 컬럼명이 바뀐 데이터 (pandas DataFrame)
result.results      # 컬럼별 판정 결과 (아래 3번 참고)
result.header_row   # 헤더가 몇 번째 줄이었는지
result.summary()    # 자동 매핑률 등
```

### ③ 컬럼 하나만 매핑 — 미리보기용

```python
r = map_column("총질소", lexicon)
```

### ④ 사람 판정 반영 — 검증 화면에서 판정했을 때

```python
apply_review("판정이_채워진_review_queue.csv", "ontology")
```

> ⚠️ 지금은 쓰지 말 것. 이유는 5번에 있다.

---

## 3. 판정 결과 읽는 법

`map_file()`이 돌려주는 컬럼 하나의 결과:

```python
r.status    # 판정 4가지 중 하나
r.code      # 표준코드 (WQ-005)
r.score     # 유사도 점수
r.site      # 지점명 (공촌천_수온 → 공촌천)
r.raw       # 원본 컬럼명
```

### status 4가지

| status | 뜻 | 화면에서 |
|---|---|---|
| `exact` | 사전에 그대로 있음 | 🟢 확정 |
| `fuzzy_auto` | 85점 이상으로 비슷함 | 🟢 확정 |
| `needs_review` | 70~85점, 애매함 | 🟡 **사람에게 물어보기** |
| `unmapped` | 모르겠음 | 🔴 **사람에게 물어보기** |

`needs_review`와 `unmapped`만 검증 화면에 띄우면 된다.

### 검증 화면 버튼 → 저장할 값

| 버튼 | 저장 |
|---|---|
| 맞음 | `승인` |
| 아님 | `기각` |
| 다른 항목 선택 | 고른 표준코드 (예: `MD-006`) |

---

## 4. 사전을 고치면 서버를 다시 켜야 한다

`load_lexicon()`은 사전을 **메모리에 한 번만** 올린다.
CSV 파일을 바꿔도 서버가 다시 켜지기 전까지는 옛날 사전을 쓴다.

**해야 할 일**: 사전을 다시 읽는 API를 하나 만들 것.

```python
POST /admin/reload-dictionary   →  lexicon = load_lexicon(...)
```

---

## 5. ⚠️ 가장 중요 — 사용자 판정을 CSV에 바로 쓰지 말 것

### 무슨 일이 생기나

사전을 고치는 사람이 **둘**이다.

```
우리 팀  →  git에 커밋
사용자   →  검증 화면에서 판정
```

사용자 판정은 서버에만 있고 git에는 없다.
이 상태에서 `git pull`을 하면 **사용자가 판정한 게 전부 사라진다.**

### 그래서 지금은

```
사용자 판정  →  DB 테이블에 쌓아만 두기  ✅
사용자 판정  →  ontology/*.csv 에 바로 쓰기  ❌
```

`apply_review()`는 CSV를 직접 고치므로 지금은 부르지 않는다.

### 판정을 쌓아둘 테이블

| 컬럼 | 예시 |
|---|---|
| 원본 컬럼명 | 구분 |
| 출처 파일 | 인천시_수질오염.csv |
| 후보 표준코드 | MD-006 |
| 점수 | 80.0 |
| 사람 판정 | MD-006 |
| 판정자 | 박서연 |
| 판정 시각 | 2026-08-07 14:32 |

### 나중에 (검증 화면 완성 후)

사전의 원본을 CSV에서 **DB로 옮긴다.** 준비는 끝나 있다.

```bash
psql -d <db> -f ontology/source/schema.sql
psql -d <db> -f ontology/source/seed.sql
```

옮긴 뒤에는 이렇게 바뀐다.

```
지금:  git이 사전의 원본
나중:  DB가 사전의 원본  (git은 코드만)
```

---

## 6. 알아둘 것

- **자동 매핑률 98.2%는 성능 보장이 아니다.** 샘플 6개 파일로 잰 값이다.
- **사전은 아직 검증 중이다.** 메타 사전 32개 중 14개가 미검증(draft) 상태다.
- **사전 CSV를 직접 고치지 말 것.** `ontology/source/`를 고치고 `export_ontology.py`를 돌린다. 자세한 건 [ontology/README.md](ontology/README.md).
- **LLM 자동 매핑은 아직 없다.** `llm_fallback()`은 빈 껍데기다.

---

## 7. 폴더 구조

```
pipeline/          매핑 엔진 ← 백엔드가 쓰는 곳
  mapper.py          매핑 알고리즘
  config.py          임계값 85 / 70
  run.py             전체 실행
  apply_review.py    판정 반영 (지금은 쓰지 않음)

ontology/          표준 사전
  *.csv              엔진이 읽는 사전 (직접 고치지 말 것)
  source/            사전의 원본 + DB 스키마

data/samples/      테스트용 실데이터 6개
tests/             테스트 (python3 -m pytest)
docs/              법령 근거 문서
```

---

## 8. 막히면

```bash
python3 -m pytest        # 35개 전부 통과하면 정상
```

궁금한 건 `docs/법령근거_목록.md`와 `ontology/README.md`에 있다.
