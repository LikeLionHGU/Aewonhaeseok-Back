# 물어볼래 백엔드

Spring Boot 4.1 · Java 21 · JPA · MySQL 8

## 구조

백엔드는 두 프로세스로 나뉜다. 매핑 엔진이 Python이라 JVM에서 직접 부를 수 없기 때문이다.

```
프론트 ──▶ 스프링부트 (여기)  ──내부 호출──▶ Python 매핑 서비스
            계정 · 파일 · 판정 · 분석         엔진 · 사전
```

프론트는 스프링만 호출한다. Python 서비스는 외부에 노출하지 않는다.

| 경로 | 내용 |
|---|---|
| `src/main/java/com/awon/backend/file/` | B2 파일 접수 |
| `src/main/java/com/awon/backend/mapping/` | B3 매핑 (Python 서비스 호출) |
| `src/main/java/com/awon/backend/review/` | B4 용어 검증 |
| `src/main/java/com/awon/backend/dictionary/` | B8 사전 버전·리로드 (중계) |
| `src/main/resources/db/migration/` | Flyway 마이그레이션 |

`pipeline/`, `ontology/`, `data/`, `docs/`는 upstream(매핑 엔진 저장소)이 관리한다.
우리가 만드는 것은 전부 `backend/` 안에 둔다. 그래야 `git merge upstream/main`에서 충돌이 안 난다.

## 처음 한 번

### 1. 데이터베이스 만들기

**문자셋은 반드시 `utf8mb4`.** MySQL의 3바이트 `utf8`은 측정 단위 표기(`㎎/L`, `℃`)와
이온 표기(`Cl⁻`)에서 깨진다. 실제 수질 데이터 컬럼명에 이런 문자가 들어온다.

```sql
CREATE DATABASE IF NOT EXISTS awon
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;
```

### 2. 접속 정보 넣기

비밀번호는 소스에 적지 않는다. 환경변수로 준다.

```bash
export DB_USER=root
export DB_PASSWORD=본인_비밀번호
```

기본값은 `localhost:3306/awon`, 사용자 `root`다. 다르면 `DB_HOST`·`DB_PORT`·`DB_NAME`도 준다.

### 3. 실행

```bash
./gradlew bootRun
```

테이블은 Flyway가 만든다. JPA의 `ddl-auto`는 `validate`로 두었다 —
스키마를 주장하는 곳이 둘이면 언젠가 어긋나기 때문이다.

## 매핑 서비스 연결

`MAPPER_BASE_URL`(기본 `http://localhost:8000`)로 Python 매핑 서비스를 찾는다.
이 서비스가 떠 있지 않으면 업로드는 되지만 매핑에서 `MAPPER_UNAVAILABLE`이 난다.

> **사전을 갱신했으면 반영을 시켜야 한다.**
> 매핑 서비스는 사전을 시작할 때 한 번만 메모리에 올린다.
> `git merge upstream/main`으로 CSV가 바뀌어도 아래를 부르기 전까지는 옛날 사전을 쓴다.
> 매핑률이 갑자기 이상하면 이것부터 확인할 것.
>
> ```
> POST /api/v1/admin/reload-dictionary
> ```

## 지켜야 할 규칙

**사용자 판정을 사전 CSV에 쓰지 않는다.** `review_items` 테이블에만 쌓는다.
사전은 git으로도 관리되므로 CSV에 쓰면 다음 merge에 판정이 전부 사라진다.
매핑 엔진의 `apply_review()`는 CSV를 직접 덮어쓰므로 서버에서 호출하면 안 된다. CLI 전용이다.

**`exact` 판정에는 점수가 없다(`score = null`).** 사전에 정확히 있었다는 뜻이지
유사도 100점이 아니다. 화면에 "100점"으로 표시하면 안 된다.

## 현재 상태

| 구분 | 상태 |
|---|---|
| B2 파일 접수 | 업로드 · 목록 · 단건 조회 |
| B3 매핑 | 실행 · 재조회 · 전후 비교 |
| B4 용어 검증 | 대기열 · 판정 저장 |
| B8 사전 운영 | 버전 조회 · 리로드 (중계) |
| 매핑 서비스 | `mapper_service/` — 구현·검증 완료 |
| B5 데이터 적재 | 세로형 변환 · 적재 · 요약 조회 |
| 판정 내보내기 | `tools/export_judgments.py` — 사전이 자라는 루프를 닫는다 |
| 인코딩 회귀 테스트 | 32개. 실파일 7개로 cp949 폴백까지 검증 |
| B6 기준치 | 미착수 — 별표 13에서 숫자 추출 선행 |
| B7 AI 분석 | 미착수 — 재료(측정값)는 갖춰짐 |
| B1 계정 | 미착수 — 인증 방식·테넌트 범위 결정 대기 |

## 다른 작업자에게 전달할 것

**표준 사전에 원폐수/방류수 구분 용어가 없다.** 2026-08-11 확인.
`시료구분`·`원폐수`·`방류수` 모두 unmapped다. 온톨로지 인수인계 문서는 이 축을
채웠다고 적었지만 실제로는 들어가 있지 않다.

같은 BOD 값이라도 처리 전이면 정상, 처리 후면 문제다. 구분 없이 집계하면
기준 초과 건수가 통째로 부풀려진다(데모 데이터에서 240건 → 15건).
지금은 원본 문자열로 받아 두었고, 사전에 등재되면 코드 컬럼으로 옮긴다.

## 두 서비스 함께 띄우기

매핑 서비스가 없으면 업로드는 되지만 매핑에서 `MAPPER_UNAVAILABLE`(503)이 난다.

```bash
# 터미널 1 — 매핑 서비스
cd backend/mapper_service && uvicorn app:app --port 8000

# 터미널 2 — 스프링
cd backend && ./gradlew bootRun --args='--spring.profiles.active=local'
```
