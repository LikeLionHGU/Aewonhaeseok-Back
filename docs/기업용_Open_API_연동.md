# 기업용 수질 표준화 Open API

## 접속 정보

- Base URL: `https://1-201-116-24.sslip.io/open-api/v1`
- 인증 헤더: `X-API-Key: awon_live_...`
- OpenAPI JSON: `https://1-201-116-24.sslip.io/v3/api-docs/enterprise-open-api`
- 파일 제한: CSV, XLS, XLSX, XLSM / 최대 100MB
- 기본 호출 제한: 키별 분당 60회

API 키 원문은 발급 응답에서 한 번만 제공된다. 서버에는 SHA-256 해시만 저장되므로 분실하면 관리자 API에서 새 키를 발급하고 기존 키를 폐기한다.

## 인증 확인

```bash
curl https://1-201-116-24.sslip.io/open-api/v1/me \
  -H "X-API-Key: awon_live_xxx"
```

## 컬럼 목록 매핑

```bash
curl -X POST https://1-201-116-24.sslip.io/open-api/v1/mappings/columns \
  -H "X-API-Key: awon_live_xxx" \
  -H "Content-Type: application/json" \
  -d '{"columns":["총질소","T-N","공촌천_수온"]}'
```

`status`는 `exact`, `fuzzy_auto`, `needs_review`, `unmapped`, `organization_exact` 중 하나다. `source=organization_dictionary`이면 해당 기업이 과거에 승인한 표현을 적용한 결과다.

## 파일 전체 매핑

```bash
curl -X POST https://1-201-116-24.sslip.io/open-api/v1/mappings/files \
  -H "X-API-Key: awon_live_xxx" \
  -F "file=@sample.xlsx"
```

업로드 파일은 매핑 중 임시 파일로만 사용하고 응답 후 삭제한다. 웹 서비스의 파일·분석 기록에는 저장되지 않는다.

## 검수 결과를 기업 사전에 추가

```bash
curl -X POST https://1-201-116-24.sslip.io/open-api/v1/reviews \
  -H "X-API-Key: awon_live_xxx" \
  -H "Content-Type: application/json" \
  -d '{"raw":"우리회사TN","standard_code":"WQ-005","note":"사내 명칭"}'
```

같은 기업에서 이후 `우리회사TN`을 매핑하면 `WQ-005`로 자동 확정된다. 다른 기업의 사전에는 영향을 주지 않는다.

기업 사전 조회:

```http
GET /open-api/v1/dictionary/terms
X-API-Key: awon_live_xxx
```

## 오류

- `401 OPEN_API_KEY_REQUIRED`: 키 헤더 누락
- `401 OPEN_API_KEY_INVALID`: 잘못됐거나 폐기된 키
- `422 STANDARD_CODE_UNKNOWN`: 공용 수질 사전에 없는 표준코드
- `429 OPEN_API_RATE_LIMITED`: 분당 호출 제한 초과, `Retry-After: 60`

모든 호출은 키·기업·경로·응답 상태·처리시간 기준으로 사용량 로그에 기록된다. API 키 원문과 업로드 파일 내용은 사용량 로그에 기록하지 않는다.

## 로그인한 기업 담당자의 키 관리

아래 경로는 `AWON_ACCESS_TOKEN` HttpOnly 쿠키 인증이 필요하며 일반 사용자 계정도 호출할 수 있다. 브라우저 요청에서는 `credentials: "include"`를 사용한다.

첫 키 발급:

```http
POST /api/v1/open-api/keys
Content-Type: application/json

{
  "organization_name": "어원환경",
  "key_name": "운영 서버",
  "requests_per_minute": 60
}
```

- `requests_per_minute`를 생략하면 60회/분이 적용된다.
- 첫 발급 시 기업이 생성되고 로그인 계정이 소유자로 연결된다.
- 이후에는 같은 `organization_name`으로 해당 기업의 키를 추가 발급한다.
- 계정이 다른 기업에 연결되어 있거나 이미 다른 사용자가 소유한 기업명을 보내면 `403 OPEN_API_ORGANIZATION_FORBIDDEN`이다.
- 기업별 활성 키는 최대 5개이며 초과 시 `409 OPEN_API_ACTIVE_KEY_LIMIT`이다.
- 응답의 `api_key` 원문은 한 번만 제공된다.

내 키 목록:

```http
GET /api/v1/open-api/keys
```

목록에는 키 원문이 없으며 `prefix`만 제공된다. 아직 기업이 연결되지 않은 계정은 빈 배열을 받는다.

내 키 폐기:

```http
DELETE /api/v1/open-api/keys/{keyId}
```

성공 시 `204 No Content`이며 다른 기업의 키에는 `403 OPEN_API_ORGANIZATION_FORBIDDEN`을 반환한다.
