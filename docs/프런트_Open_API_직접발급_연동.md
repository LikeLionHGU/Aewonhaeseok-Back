# 프런트엔드 Open API 직접 발급 연동

## 인증

세 경로 모두 기존 로그인 쿠키 `AWON_ACCESS_TOKEN` 인증이 필요합니다. 프런트 요청에는 반드시 `credentials: "include"`를 사용합니다.

로그인하지 않은 요청은 다음과 같이 거절됩니다.

```text
401 AUTH_REQUIRED
```

## 1. 내 API 키 발급

```http
POST /api/v1/open-api/keys
Content-Type: application/json
```

```json
{
  "organization_name": "어원환경",
  "key_name": "운영 서버",
  "requests_per_minute": 60
}
```

`requests_per_minute`는 생략할 수 있으며 기본값은 60입니다. 일반 사용자 직접 발급은 최대 60회/분입니다.

```javascript
const response = await fetch(`${API_BASE_URL}/api/v1/open-api/keys`, {
  method: "POST",
  credentials: "include",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    organization_name: "어원환경",
    key_name: "운영 서버",
    requests_per_minute: 60
  })
});
```

성공 시 `201 Created`이며 기존 관리자 발급 응답과 동일합니다.

```json
{
  "organization": {
    "id": 1,
    "name": "어원환경",
    "active": true,
    "created_at": "2026-08-21T21:00:00+09:00"
  },
  "key": {
    "id": 1,
    "name": "운영 서버",
    "prefix": "awon_live_example",
    "active": true,
    "requests_per_minute": 60,
    "created_at": "2026-08-21T21:00:00+09:00"
  },
  "api_key": "awon_live_발급직후에만제공되는원문",
  "warning": "이 키는 다시 조회할 수 없습니다. 안전한 비밀 저장소에 보관하세요."
}
```

`api_key`는 발급 직후 모달에서 한 번만 보여주고 프런트 저장소, 브라우저 Local Storage 또는 소스 코드에 저장하지 않습니다.

## 2. 내 API 키 목록

```http
GET /api/v1/open-api/keys
```

```javascript
const response = await fetch(`${API_BASE_URL}/api/v1/open-api/keys`, {
  credentials: "include"
});
const keys = await response.json();
```

- 로그인 계정이 소유한 기업의 키만 반환합니다.
- 키 원문은 반환하지 않고 `prefix`만 반환합니다.
- 아직 키를 발급하지 않은 계정은 `[]`를 받습니다.

## 3. 내 API 키 폐기

```http
DELETE /api/v1/open-api/keys/{keyId}
```

```javascript
await fetch(`${API_BASE_URL}/api/v1/open-api/keys/${keyId}`, {
  method: "DELETE",
  credentials: "include"
});
```

성공 시 `204 No Content`입니다. 자기 기업의 키만 폐기할 수 있습니다.

## 소유권 및 제한

- 첫 발급 시 기업을 생성하고 로그인 계정을 해당 기업의 소유자로 연결합니다.
- 같은 계정의 추가 발급은 처음 등록한 기업명과 동일해야 합니다.
- 다른 사용자가 이미 소유한 기업명으로는 키를 발급할 수 없습니다.
- 다른 기업의 키는 조회하거나 폐기할 수 없습니다.
- 기업당 활성 키는 최대 5개입니다.

## 프런트에서 처리할 오류

| HTTP | 코드 | 의미 |
|---:|---|---|
| 400 | `VALIDATION_FAILED` | 회사명·키 이름 또는 호출 한도 입력값 오류 |
| 401 | `AUTH_REQUIRED` | 로그인 필요 |
| 403 | `OPEN_API_ORGANIZATION_FORBIDDEN` | 다른 기업명 사용 또는 다른 기업 키 접근 |
| 409 | `OPEN_API_ACTIVE_KEY_LIMIT` | 활성 키 5개 초과 |

## 발급 완료 화면

발급 성공 응답의 `api_key`와 `warning`을 모달에 표시합니다. 사용자가 모달을 닫은 후에는 키 목록 API의 `prefix`만 보여줍니다.

기업이 실제 Open API를 호출할 때는 발급받은 키를 기업의 백엔드 서버에서 `X-API-Key` 헤더로 전송합니다. 브라우저 프런트엔드에서 기업용 API 키로 `/open-api/v1/*`를 직접 호출하지 않습니다.
