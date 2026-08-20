# 프런트 회원인증·사용자별 데이터 연동 가이드

## 1. 핵심 계약

- 운영 API HTTPS 주소: `https://1-201-116-24.sslip.io/api/v1`
- 실제 웹에서는 기존과 같이 같은 출처의 `/api/v1` 프록시 경로 사용을 권장한다.
- JWT는 응답 JSON에 포함되지 않고 `AWON_ACCESS_TOKEN` HttpOnly 쿠키에만 저장된다.
- 프런트는 토큰을 localStorage/sessionStorage에 저장하거나 직접 해석하지 않는다.
- 로그인한 사용자의 파일·매핑·측정값·검토·분석 이력만 서버에서 자동 조회된다.
- 다른 사용자의 파일 ID, 검토 ID, 분석 execution ID를 보내면 존재 여부를 숨기기 위해 `404`가 반환된다.

운영 서버는 `AUTH_REQUIRED=true`다. 로그인 쿠키가 없거나 만료되면 데이터 API가 `401 AUTH_REQUIRED`를 반환한다.

## 2. 인증 API

### 회원가입

`POST /api/v1/auth/register`

```json
{
  "email": "user@example.com",
  "password": "password123",
  "display_name": "홍길동"
}
```

성공 `200`:

```json
{
  "id": 2,
  "email": "user@example.com",
  "display_name": "홍길동",
  "role": "USER"
}
```

응답 헤더가 로그인 쿠키를 설정하므로 회원가입 직후 로그인 상태다. 이메일 중복은 `409 AUTH_EMAIL_ALREADY_USED`다. 비밀번호는 8~72자다.

### 로그인

`POST /api/v1/auth/login`

```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

성공 응답은 회원가입과 같은 사용자 객체이며 `Set-Cookie`로 JWT가 설정된다. 실패는 `401 AUTH_INVALID_CREDENTIALS`다.

### 현재 사용자

`GET /api/v1/auth/me`

로그인 상태면 사용자 객체, 아니면 `401 AUTH_REQUIRED`를 반환한다. 앱 시작 시 로그인 여부 복원에 사용한다.

### 로그아웃

`POST /api/v1/auth/logout`

```json
{ "logged_out": true }
```

만료 쿠키를 설정한다. 로그아웃 직후에는 `/auth/me`를 다시 호출할 필요 없이 프런트 사용자 상태를 비우면 된다.

## 3. fetch 설정

운영·개발 모두 같은 출처 프록시(`/api/v1`)를 사용한다. 현재 쿠키는 `SameSite=Strict`이므로 `deno.net` 화면에서 별도 API 도메인을 브라우저가 직접 호출하는 구조가 아니라, 프런트 서버가 `/api/v1`을 HTTPS API로 프록시해야 한다. 개발 Vite 프록시뿐 아니라 운영 호스팅의 서버 라우트·리라이트에도 같은 프록시가 필요하다.

```ts
export async function api(path: string, init: RequestInit = {}) {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    credentials: "include",
    headers: {
      ...(init.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...init.headers,
    },
  });

  if (response.status === 401) {
    // 로그인 화면으로 이동하거나 로그인 모달 표시
  }
  return response;
}
```

업로드 예시:

```ts
const form = new FormData();
form.append("file", file);
await api("/files", { method: "POST", body: form });
```

`Authorization` 헤더를 프런트가 만들 필요는 없다.

## 4. 기존 데이터 API 변경점

URL과 요청/응답 형식은 바뀌지 않았다. 아래 API에 사용자 필터가 서버에서 자동 적용된다.

- `POST/GET /files`, `GET /files/{id}`, `GET /files/{id}/preview`
- `POST/GET /files/{fileId}/mapping`, `GET /files/{fileId}/mapping/summary`
- `POST /files/{fileId}/ingest`, `GET /measurements/summary`
- `GET /reviews`, `POST /reviews/{id}/verdict`
- `POST/GET /analyses`, `GET /analyses/options`, `GET /analyses/{executionId}`
- `GET /analyses/{executionId}/measurements`
- `GET /standards/exceedances`

법령 기준 자체인 `/standards`, `/standards/limits`와 용어 사전 조회는 모든 사용자에게 공통이다.

로그인 상태의 검토 판정자는 요청의 `reviewed_by` 대신 로그인한 사용자의 `display_name`을 서버가 기록한다. 기존 프런트 호환을 위해 필드 전송은 당분간 허용된다.

## 5. 프런트 구현 순서

1. 공통 API 호출에 `credentials: "include"` 적용
2. 회원가입·로그인 화면 연결
3. 앱 시작 시 `/auth/me`로 세션 복원
4. `401` 공통 처리와 로그인 화면 이동
5. 로그아웃 연결
6. 서로 다른 두 계정으로 파일·분석·검토 목록이 섞이지 않는지 확인
7. 배포 환경에서도 `/api/v1` HTTPS 프록시와 쿠키 전달 여부 확인

## 6. Swagger와 오류 형식

- Swagger UI: `https://1-201-116-24.sslip.io/swagger-ui/index.html`
- OpenAPI JSON: `https://1-201-116-24.sslip.io/v3/api-docs`

공통 오류:

```json
{
  "error": {
    "code": "AUTH_REQUIRED",
    "message": "로그인이 필요합니다.",
    "detail": {}
  }
}
```

운영 웹과 API는 모두 HTTPS이며 운영 쿠키는 `HttpOnly; Secure; SameSite=Strict`다. Deno 운영 프록시는 `https://1-201-116-24.sslip.io`를 대상으로 하고, 백엔드의 `Set-Cookie` 응답 헤더와 요청의 `Cookie` 헤더를 제거하지 않아야 한다.
