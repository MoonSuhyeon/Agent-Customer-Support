# bank-transfer-demo

## 컨벤션

### 금액
- TypeScript 타입은 `number`지만 의미상 원 단위 정수 (BigInt 수준 정밀도)
- API 전송/수신 시 `string`으로 직렬화 (`"1000000"`)
- 화면 표시 시 `Intl.NumberFormat` 사용

### 시간 필드
- 접미사 `_at` 사용 (`created_at`, `transferred_at` 등)
- ISO 8601 문자열로 전송

### API 응답
- 백엔드 팀 표준 형식 따름 (확정 시 이 파일 업데이트)

## 디렉토리 구조

| 경로 | 역할 |
|------|------|
| `app/transfer/` | 이체 관련 페이지 (Next.js App Router) |
| `components/features/` | 도메인별 UI 컴포넌트 (features/transfer 등) |
| `components/ui/` | shadcn/ui 공용 컴포넌트 |
| `lib/api/` | fetch 래퍼 + JWT 헤더 자동 주입 |
| `lib/schemas/` | Zod 폼 스키마 모음 |
| `mocks/` | MSW 핸들러 (handlers.ts) |

## 규칙
- 컴포넌트는 `features/<도메인>/` 아래에 배치
- 폼 스키마는 `lib/schemas/` 에만 정의
- API 호출은 반드시 `lib/api/client.ts` 의 `apiClient` 사용
