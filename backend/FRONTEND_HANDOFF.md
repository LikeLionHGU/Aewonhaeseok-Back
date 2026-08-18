# 프런트 연동 변경사항

배포 기준 API 주소: `http://100.62.74.158/api/v1`

Swagger UI: `http://100.62.74.158/swagger-ui/index.html`

## 새로 사용할 API

- `GET /dictionary/terms?query=BOD&dict_type=측정항목`
  - 표준코드 선택창의 이름/코드 검색
- `GET /analyses/{execution_id}/measurements?page=1&size=50`
  - 분석 결과의 근거가 된 원본 측정 행 조회
- `GET /files`
  - 각 파일에 `measured_from`, `measured_to`, `dictionary_version`, `auto_mapped_rate` 추가

## 분석 조건 변경

`POST /analyses` 요청에 배출규모 `scale`을 선택적으로 보낼 수 있습니다.

- `large`: 1일 폐수배출량 2,000㎥ 이상
- `small`: 1일 폐수배출량 2,000㎥ 미만

```json
{
  "item_codes": ["WQ-001", "WQ-002"],
  "region_grade": "가지역",
  "scale": "small",
  "bucket": "month",
  "metric": "avg"
}
```

`region_grade` 또는 `scale`을 생략하면 서버가 임의 기준을 선택하지 않습니다. 규모와
무관한 pH·총질소·총인 기준만 반환될 수 있으며, `assumptions`에 생략 사실이 포함됩니다.

선택지는 `GET /analyses/options` 또는 `GET /standards`의 `scales`를 사용하세요.

`GET /analyses`의 `conditions`는 이제 JSON 문자열이 아니라 요청과 같은 JSON 객체로
내려갑니다. 별도의 `JSON.parse()` 처리는 필요하지 않습니다.

## 검토 판정 API

`POST /reviews/{review_id}/verdict`의 `verdict`에는 다음 두 형태를 사용하세요.

- 표준코드 선택: 사용자가 선택한 코드(예: `WQ-001`)
- 매칭 없음: `no_match`

`no_match`는 후보를 승인하는 의미가 아니며 해당 원문을 미매핑 상태로 확정합니다.
기존 클라이언트 호환을 위해 `approved`, `rejected`, `승인`, `기각` 입력도 받지만,
응답과 저장 값은 표준코드 또는 `no_match`로 정규화됩니다.

Swagger/OpenAPI의 모든 응답 필드명은 실제 API와 동일한 `snake_case`로 제공됩니다.

## 기준치 API

- `GET /standards/limits?region_grade=가지역&scale=small`
- `GET /standards/exceedances?region_grade=가지역&scale=small&file_id=1`

`GET /standards/limits`의 `scale`은 필수입니다. `large` 또는 `small`을 반드시 보내야 하며,
누락하거나 빈 값으로 보내면 HTTP 400을 반환합니다. 선택한 규모를 보내면 pH·총질소·총인
공통 기준과 BOD·TOC·부유물질의 해당 규모 기준이 함께 반환됩니다.

현행 일반 배출허용기준은 `source=law`로 내려갑니다. 총질소 등은 업종에 따라 별도
기준이 적용될 수 있으므로 사업장 업종 조건이 없는 현재 버전의 결과는 일반 기준 판정입니다.

## 오류 처리

- 잘못된 JSON·날짜·파라미터: HTTP 400
- 파일 업로드 Content-Type이 multipart/form-data가 아님: HTTP 415
- 잘못된 검토 상태 또는 규모 값: HTTP 400
- 사전에 없는 검토 표준코드: HTTP 422

오류 본문은 공통적으로 `error.code`, `error.message`, `error.details` 형태입니다.
