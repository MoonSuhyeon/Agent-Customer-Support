# 은행 이체 워밍업 프로젝트

본 프로젝트의 본격 진행 전, 핵심 패턴을 익히기 위한 워밍업 프로젝트입니다.

## 기술 스택
- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS + shadcn/ui
- TanStack Query
- React Hook Form + Zod
- MSW (Mock Service Worker)

## 주요 기능
- 회원 관리
- 계좌 조회 (대시보드, 계좌 상세)
- 이체 (입력 → 확인 → 결과)
- 거래 내역
- 대출 신청
- 설정

## 데이터 모델 (ERD)

![ERD](./docs/erd.png)

자세한 설명은 [docs/erd-notes.md](./docs/erd-notes.md) 참고.

## 디렉토리 구조
```
app/
  (main)/
    dashboard/
    accounts/
    transfer/
    loans/
    settings/
components/
  ui/                # shadcn 컴포넌트
  features/          # 도메인별 컴포넌트
lib/
  api/               # API 클라이언트
  schemas/           # Zod 스키마
mocks/               # MSW 핸들러
docs/                # 문서 (ERD 등)
```

## 명명 규칙

- 테이블 prefix (acct_, txn_, tfr_, loan_)
- 컬럼: [수식어]+[핵심어]+[도메인]
- 금액: BIGINT, 원 단위
- 시간: TIMESTAMPTZ + _at
- soft delete: deleted_at IS NULL

## 실행 방법

```bash
npm install
npm run dev
```

브라우저에서 http://localhost:3000 접속
