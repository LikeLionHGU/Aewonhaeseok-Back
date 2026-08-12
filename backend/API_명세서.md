# 물어볼래 — 백엔드 API 명세서 (초안 v0.1)

작성 기준: 기능명세서(2026-08-07) + 매핑 엔진 저장소 실측
대상 독자: 프론트엔드 작업자

이 문서는 **확정 / 잠정 / 결정 필요** 세 등급으로 표시한다.

- ✅ **확정** — 매핑 엔진 코드가 응답 형태까지 정해놓은 것. 바꿀 일 없다.
- 🟡 **잠정** — 설계는 됐으나 구현하며 바뀔 수 있다. 프론트는 붙여도 되지만 필드 추가를 예상할 것.
- ❌ **결정 필요** — 제품 결정이 없어 아직 못 쓴다.

---

## 0. 공통 규약

### 기본
- Base URL: `/api/v1`
- 요청·응답 모두 `application/json` (파일 업로드만 `multipart/form-data`)
- 문자 인코딩 UTF-8. **응답 JSON의 한글은 이스케이프하지 않는다** (`ensure_ascii=false`)
- 시각은 전부 ISO 8601 + KST 오프셋: `2026-08-09T14:32:00+09:00`

### 에러 형식 🟡

모든 4xx·5xx는 동일한 형태로 응답한다.

```json
{
  "error": {
    "code": "FILE_ENCODING_UNSUPPORTED",
    "message": "CSV 인코딩을 인식하지 못했습니다.",
    "detail": { "tried": ["utf-8-sig", "cp949", "euc-kr"] }
  }
}
```

`message`는 화면에 그대로 띄울 수 있는 한국어 문장으로 준다. 프론트가 문구를 새로 만들지 않아도 되게 한다.

주요 에러 코드:

| HTTP | code | 상황 |
|---|---|---|
| 400 | `FILE_ENCODING_UNSUPPORTED` | CSV 인코딩 판별 실패 |
| 400 | `FILE_FORMAT_UNSUPPORTED` | xlsx/xlsm/xls/csv 외 확장자 |
| 404 | `FILE_NOT_FOUND` | 파일 id 없음 |
| 409 | `MAPPING_ALREADY_RUNNING` | 같은 파일에 매핑 중복 요청 |
| 422 | `VERDICT_CODE_UNKNOWN` | 판정에 적힌 표준코드가 사전에 없음 |
| 500 | `DICTIONARY_CONFLICT` | 사전 표기 충돌 (엔진이 `DictionaryConflictError`를 던짐) |

### 페이징 🟡
목록 응답은 `?page=1&size=20`. 응답에 `{"items": [...], "page": 1, "size": 20, "total": 137}`.

---

## 1. B2 — 파일 접수

### `POST /files` 🟡 업로드

`multipart/form-data`, 필드명 `file`. xlsx / xlsm / xls / csv만 허용.

**원본 파일은 절대 수정하지 않고 그대로 보관한다** (감사 대응). 매핑 결과는 별도로 저장한다.

응답 `201`:
```json
{
  "id": 41,
  "filename": "충남_보건환경연구원_물환경측정망_하천.csv",
  "size_bytes": 148701,
  "content_type": "text/csv",
  "encoding_detected": "cp949",
  "header_row": 1,
  "status": "uploaded",
  "uploaded_at": "2026-08-09T14:32:00+09:00"
}
```

`status`: `uploaded` → `mapping` → `mapped` → `reviewing` → `completed`

> **주의** — 업로드 시점에 인코딩 판별과 헤더 탐지까지 수행한다. 여기서 실패하면 `400`을 주고 파일을 저장하지 않는다. 엔진의 인코딩 폴백 순서는 `utf-8-sig → cp949 → euc-kr`이고, **이 경로에는 아직 테스트가 없어 가장 먼저 깨질 수 있는 지점이다.**

### `GET /files` 🟡 목록

`?status=mapped&page=1&size=20`

```json
{
  "items": [
    {
      "id": 41,
      "filename": "충남_보건환경연구원_물환경측정망_하천.csv",
      "status": "reviewing",
      "uploaded_at": "2026-08-09T14:32:00+09:00",
      "column_count": 69,
      "pending_review_count": 1
    }
  ],
  "page": 1, "size": 20, "total": 7
}
```

`pending_review_count`는 프론트 화면 흐름의 "확인 필요 N건" 배지에 그대로 쓴다.

### `GET /files/{id}` 🟡 단건 + 원본 미리보기

응답에 `preview` 필드로 원본 상위 10행을 넣는다. 용어 검증 화면에서 "실제 값 미리보기"가 필수라고 명세서가 못박았기 때문이다(인천·제주의 `구분` 같은 컬럼은 이름만으로 판단 불가).

---

## 2. B3 — 매핑

### `POST /files/{id}/mapping` ✅ 매핑 실행

요청 본문 없음.

**동기 응답으로 처리한다.** 실측 근거: 9.08MB / 104만 행 파일이 **0.33초**, 나머지 파일은 전부 0.06초 이하. 사전 로딩도 0.019초다. 작업 큐를 둘 이유가 없다.

응답 `200` — 필드 구성은 엔진의 `build_report()`와 `MappingResult`를 그대로 따른다.

```json
{
  "file_id": 41,
  "header_row": 1,
  "dictionary_version": "dict-2026-08-08",
  "summary": {
    "total_columns": 69,
    "auto_mapped": 61,
    "needs_review": 1,
    "unmapped": 7,
    "auto_mapped_rate": 88.4,
    "needs_review_rate": 1.4,
    "unmapped_rate": 10.1
  },
  "columns": [
    {
      "raw": "공촌천_수온",
      "normalized": "공촌천_수온",
      "status": "exact",
      "via": "composite",
      "code": "WQ-009",
      "site": "공촌천",
      "output_column": "WQ-009@공촌천",
      "matched_variant": "온도",
      "score": null,
      "dict_type": "측정항목"
    }
  ]
}
```

**`status` 4종** — 화면 처리 규칙이 여기 달려 있다.

| status | 뜻 | 화면 |
|---|---|---|
| `exact` | 사전에 그대로 있음 | 🟢 확정 |
| `fuzzy_auto` | 85점 이상 | 🟢 확정 |
| `needs_review` | 70~85점, 애매함 | 🟡 검증 화면에 노출 |
| `unmapped` | 판단 불가 | 🔴 검증 화면에 노출 |

`score`는 **`exact`일 때 항상 `null`**이다. 점수로 확정한 게 아니라 사전에 정확히 있었다는 뜻이므로, 화면에 "100점"으로 표시하면 안 된다.

`via`는 `body` / `paren` / `composite` 중 하나이며 판정 근거를 설명한다. `composite`는 `{지점명}_{측정항목}` 형태를 분해했다는 뜻이고, 이때만 `site`가 채워진다.

### `GET /files/{id}/mapping` ✅ 결과 재조회
위와 동일한 응답. 매핑을 다시 돌리지 않고 저장된 결과를 준다.

### `GET /files/{id}/mapping/summary` 🟡 전후 비교

**발표 핵심 지표.** 판정 반영 전후로 매핑률이 얼마나 올랐는지 보여준다.

```json
{
  "file_id": 41,
  "rounds": [
    { "round": 1, "dictionary_version": "dict-2026-08-08", "auto_mapped_rate": 88.4, "ran_at": "..." },
    { "round": 2, "dictionary_version": "dict-2026-08-11", "auto_mapped_rate": 92.8, "ran_at": "..." }
  ],
  "delta": 4.4
}
```

---

## 3. B4 — 용어 검증

> ⚠️ **이 영역의 절대 규칙** — 사용자 판정을 사전 CSV에 직접 쓰지 않는다.
> 사전은 git으로도 관리되므로 CSV에 쓰면 다음 merge 때 판정이 전부 사라진다.
> 엔진의 `apply_review()`는 CSV를 직접 덮어쓰므로 **웹에서 절대 호출하지 않는다.** CLI 전용이다.
> 판정은 DB 테이블에만 적재한다.

### `GET /reviews` 🟡 검증 대기열

`?file_id=41&status=pending`

`needs_review`와 `unmapped`만 나온다. 컬럼명만으로는 판단이 불가능하므로 **실제 값 요약을 반드시 함께 준다.**

```json
{
  "items": [
    {
      "id": 88,
      "file_id": 41,
      "filename": "충남_보건환경연구원_물환경측정망_하천.csv",
      "raw": "채수시각\n(WMCTM)",
      "mapping_status": "needs_review",
      "candidate_code": "MD-006",
      "candidate_name": "측정일자",
      "score": 80.0,
      "value_summary": {
        "row_count": 1980,
        "distinct_count": 24,
        "samples": ["09:30", "10:00", "10:30"],
        "all_unique": false
      },
      "verdict": null
    }
  ]
}
```

> **함정 사례** — 위 `채수시각`은 후보 MD-006(측정**일자**)이 80점으로 나오지만 정답은 MD-012(측정**시각**)다. 홀드아웃 판정 가이드에 기록된 실제 사례다. **점수가 높다고 승인하면 안 된다**는 걸 화면에서 사용자에게 알려줘야 한다.

### `POST /reviews/{id}/verdict` 🟡 판정 저장

```json
{ "verdict": "MD-012", "note": "측정일자가 아니라 측정시각임" }
```

`verdict`에 들어갈 값 — 화면 버튼과 1:1 대응한다.

| 버튼 | 보낼 값 |
|---|---|
| 맞음 | `"승인"` |
| 아님 | `"기각"` |
| 다른 항목 선택 | 고른 표준코드 (`"MD-012"`) |

판정자와 판정 시각은 **서버가 자동으로 기록한다.** 프론트가 보내지 않는다.

응답 `200`:
```json
{
  "id": 88,
  "verdict": "MD-012",
  "reviewed_by": "박서연",
  "reviewed_at": "2026-08-09T14:32:00+09:00",
  "applied_to_dictionary": false
}
```

`applied_to_dictionary`는 항상 `false`로 시작한다. 판정이 실제 사전에 반영되는 건 팀이 CLI로 별도 처리하는 단계이고, 그때 `true`가 된다.

### `GET /standards` ❌ 기준 세트 조회 — B6 선행 필요

배출허용기준 / 하천 생활환경기준 등 세트 목록. **현재 사전에는 기준치 숫자가 없다.** 측정항목 사전 17개 컬럼 어디에도 없고 법령 조항 이름만 문자열로 들어 있다. 별표 13과 환경기준에서 숫자를 추출해 테이블을 새로 만들어야 한다.

---

## 4. B8 — 사전 운영

### `GET /dictionary/version` ✅

응답은 엔진 `version.py`의 `as_dict()`를 **그대로** 내보낸다. 손대지 않는다.

```json
{
  "version": "dict-2026-08-08",
  "content_hash": "1af5033c93a71ac5",
  "generated_at": "2026-08-08",
  "counts": {
    "measurement_terms": 75,
    "metadata_terms": 32,
    "synonyms": 206,
    "verified_terms": 93
  },
  "excluded_inferred": false
}
```

`version`을 결과 페이지의 "사전 버전" 표시에 그대로 쓴다.

### `POST /admin/reload-dictionary` ✅

사전은 서버 시작 시 1회만 메모리에 올라간다. git merge로 CSV가 바뀌어도 이 API를 부르기 전까지는 옛날 사전을 쓴다.

리로드 판단은 `version.py`의 `is_stale()`이 내용 해시로 처리한다. 파일 수정 시각이 아니라 내용을 보므로 같은 내용을 다시 export해도 불필요한 리로드가 일어나지 않는다. 실측상 사전 로딩은 0.019초라 별도 최적화가 필요 없다.

```json
{ "reloaded": true, "from": "dict-2026-08-08", "to": "dict-2026-08-11" }
```

이미 최신이면 `{"reloaded": false, ...}`.

---

## 5. B5 / B6 / B7 — 아직 못 쓰는 부분

### B5 데이터 적재 ❌
가로형→세로형 변환, 날짜 컬럼 결합, 단위 변환, 품질 검증, 측정값 테이블. **현재 `schema.sql`은 사전 저장용 5개 테이블뿐이고 측정값을 담을 테이블이 없다.** 스키마 설계가 API보다 먼저다.

### B6 기준치 ❌
위 `GET /standards` 참조. 법령에서 숫자 추출이 선행 작업.

### B7 AI 분석 ❌
`POST /analyses/parse`, `POST /analyses`, `GET /analyses`. B5 스키마가 확정돼야 SQL 생성의 대상이 정해진다.

가드레일은 기능명세서가 이미 잡아놨고 그대로 따른다 — 읽기 전용 DB 계정, SELECT만 허용, 타임아웃, 반환 행 수 제한. 실행 이력에는 **실행 ID·규칙 버전·사전 버전을 함께 기록**한다.

> 권고: 자연어 파싱(`/analyses/parse`)을 빼고 조건 선택 UI만으로 먼저 완성할 것. 조건 확인 페이지는 디자인이 이미 완료돼 있고, 파싱 없이도 사용자가 지점·항목·기간을 고르면 결과가 나온다. 파싱은 나머지가 다 돌아간 뒤 얹는다.

---

## 6. B1 — 계정 ❌ 결정 필요

`POST /auth/signup`, `POST /auth/login`. 이메일·비밀번호·소속 기관.

**아래가 정해지지 않아 명세를 쓸 수 없다.**

1. **인증 방식** — JWT 액세스 토큰인가, 세션 쿠키인가. 프론트 작업자와 합의 필요.
2. **소속 기관이 테넌트인가** — 같은 기관 사용자끼리 업로드한 파일과 분석 결과를 공유하는가, 아니면 개인별로 격리하는가. 이 답에 따라 위의 **모든 목록 API에 기관 필터가 들어가야 한다.** 지금 명세는 필터가 없는 상태로 쓰여 있다.
3. **판정자 신원** — `POST /reviews/{id}/verdict`가 판정자를 자동 기록하는데, 로그인 사용자를 쓰는 게 맞는지. 사전의 신뢰도와 직결되는 기록이라 확인이 필요하다.

데모까지 시간이 빠듯하면 인증은 최소한으로 만들고 뒤로 미뤄도 된다. 위 흐름 중 인증에 막히는 건 없다.

---

## 7. 구현 순서 (제안)

기능명세서의 개발 순서에는 B2·B4·B1이 빠져 있어 아래로 조정한다.

1. **B2 파일 접수** — 인코딩 회귀 테스트를 먼저 작성
2. **B3 매핑 API** — 엔진 래핑, 사실상 직렬화 작업
3. **B4 용어 검증 + 전후 비교** — 핵심 차별점. 여기까지가 1차 데모
4. **B5 데이터 적재** — 스키마 설계부터
5. **B6 기준치** — 법령에서 숫자 추출
6. **B7 분석** — 조건 선택 방식 먼저, 자연어 파싱은 마지막
7. **B1 계정** — 위 결정 사항이 정해지는 대로

1~3이 끝나면 "제각각인 데이터를 넣으면 표준화되고, 애매한 건 사람이 판정하며, 그 판정으로 사전이 성장한다"는 이야기가 완성된다. 심사에서 가장 강한 카드를 일찍 손에 쥐는 순서다.

---

## 부록 — 기술 스택 전제

- **FastAPI** — 엔진이 Python이라 같은 프로세스에서 직접 호출 가능. 별도 IPC 불필요.
- **PostgreSQL** — 저장소의 `ontology/source/schema.sql`이 Postgres 전용이다. `pg_trgm` 확장과 생성 컬럼을 쓴다.
- 파일 저장은 초기엔 로컬 디스크. 원본 보존 요구가 있으므로 경로와 해시를 DB에 기록한다.

> `schema.sql` 첫 적재 시 알려진 블로커 2건:
> `term_synonyms`의 `synonym_type='deprecated_std_name'` 2행이 스키마의 CHECK 목록에 없어 실패하고, `seed.sql`은 `term_sources` 외에는 멱등하지 않아 재실행 시 PK 충돌이 난다. 둘 다 수정은 간단하나 첫 로드에서 바로 막힌다.
