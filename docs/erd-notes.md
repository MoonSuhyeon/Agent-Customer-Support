# ERD 설명

> Source: `docs/data-snapshot.md` → `docs/erd.dbml`  
> 시각화: https://dbdiagram.io 에 `erd.dbml` 내용 붙여넣기

---

## 엔티티 목록

| 테이블명 | 한글명 | 설명 | 소속 서비스 |
|---|---|---|---|
| `usr_user` | 사용자 | 회원 기본 정보 및 인증 | Customer Service |
| `usr_notification_setting` | 알림 설정 | 사용자별 알림 수신 설정 | Customer Service |
| `acct_account` | 계좌 | 예금 계좌 원장 | Deposit Service |
| `txn_transaction` | 거래 내역 | 계좌별 입출금 기록 | Deposit Service |
| `tfr_transfer` | 이체 | 계좌 간 송금 트랜잭션 | Transfer Service |
| `loan_product` | 대출 상품 | 판매 중인 대출 상품 카탈로그 | Loan Service |
| `loan_loan` | 대출 | 실행된 대출 계약 | Loan Service |
| `loan_application` | 대출 신청 | 대출 심사 신청 이력 | Loan Service |

---

## 주요 관계

```
usr_user 1 : N acct_account
  한 사용자는 여러 계좌를 보유할 수 있다.
  acct_account.user_id → usr_user.user_id

acct_account 1 : N txn_transaction
  한 계좌는 여러 거래 내역을 가진다.
  txn_transaction.account_id → acct_account.account_id

tfr_transfer 1 : 2 txn_transaction
  이체 1건은 출금 거래(from) + 입금 거래(to) 2개의 txn_transaction을 생성한다.
  txn_transaction.transfer_id → tfr_transfer.transfer_id (nullable)

usr_user 1 : N tfr_transfer
  한 사용자는 여러 이체를 발생시킬 수 있다.
  tfr_transfer.user_id → usr_user.user_id

tfr_transfer N : 1 acct_account (출금 측)
  tfr_transfer.from_account_id → acct_account.account_id

tfr_transfer N : 1 acct_account (입금 측, 내부 계좌일 때만)
  tfr_transfer.to_account_id → acct_account.account_id (nullable)

loan_product 1 : N loan_loan
  한 상품으로 여러 대출 계약이 체결될 수 있다.
  loan_loan.product_id → loan_product.product_id

loan_product 1 : N loan_application
  한 상품에 여러 신청이 들어올 수 있다.
  loan_application.product_id → loan_product.product_id

loan_application 1 : 1 loan_loan
  승인된 신청 1건은 대출 계약 1건을 생성한다.
  loan_application.loan_id → loan_loan.loan_id (nullable, 승인 시 채워짐)

usr_user 1 : 1 usr_notification_setting
  한 사용자는 하나의 알림 설정을 갖는다.
  usr_notification_setting.user_id → usr_user.user_id (unique)
```

---

## 명명 규칙

### 테이블 prefix

| prefix | 도메인 | 소속 서비스 |
|---|---|---|
| `usr_` | 사용자 (User) | Customer Service |
| `acct_` | 계좌 (Account) | Deposit Service |
| `txn_` | 거래 (Transaction) | Deposit Service |
| `tfr_` | 이체 (Transfer) | Transfer Service |
| `loan_` | 대출 (Loan) | Loan Service |

### 컬럼 규칙

| 규칙 | 예시 |
|---|---|
| PK: `{테이블단수명}_id` | `user_id`, `account_id`, `transfer_id` |
| FK: 참조 테이블의 PK명 그대로 사용 | `account_id`, `user_id` |
| 금액: `bigint`, 원 단위 정수 | `account_balance`, `transfer_amount` |
| 연이율: `decimal(5,2)`, % 단위 | `interest_rate`, `min_rate` |
| 시간: `timestamptz` + `_at` 접미사 | `created_at`, `transaction_at` |
| 날짜만: `date` + `_date` 접미사 | `next_payment_date` |
| Soft delete: `deleted_at timestamptz` | 법적 보존 필요 테이블에만 적용 |

---

## 주요 결정 사항

### 1. `counterparty_name`을 별도 테이블로 분리하지 않음

거래 상대방이 외부 은행 계좌일 수 있어 `acct_account` FK 연결이 불가능하다.  
내부 계좌인 경우에도 거래 시점의 계좌 명의를 스냅샷으로 보존해야 하므로 단순 문자열로 저장.

### 2. `txn_transaction`과 `tfr_transfer`를 별도 테이블로 분리

- `txn_transaction`: 단일 계좌 관점의 원장. 모든 입출금(이체 포함, ATM, 이자 등) 기록.
- `tfr_transfer`: 두 계좌를 연결하는 송금 트랜잭션. 이체 1건이 `txn_transaction` 2건(출금 + 입금)을 생성.
- 분리하면 "이체 아닌 거래"도 자연스럽게 표현 가능하고, 이체 전용 조회(idempotency, 상태 추적)가 명확해진다.

### 3. `to_account_no` + `to_account_id` 이중 설계

- `to_account_no`: 항상 존재. 사용자가 입력한 계좌번호 원문 보존. 외부 은행 이체도 수용.
- `to_account_id`: nullable. 입금 계좌가 내부 계좌일 때만 채워짐 (FK 조인 가능).
- 외부 은행 이체 시 `to_account_id = NULL`, 내부 이체 시 양쪽 모두 채워짐.

### 4. `loan_application`과 `loan_loan` 분리

- `loan_application`: 심사 과정 이력. PENDING/APPROVED/REJECTED 상태를 모두 보존.
- `loan_loan`: 실행된 대출 계약. APPROVED된 신청만 대응하는 loan_loan을 갖는다.
- 분리하면 탈락 심사 이력을 보관하면서 실행 중인 대출만 별도 관리 가능.

### 5. 금액을 `bigint`로 설계

원 단위 정수 저장. `decimal`/`float`의 부동소수점 오류를 방지.  
현재 mock에서도 금액을 string으로 직렬화하여 정밀도 손실 없이 전달.

### 6. Soft delete (`deleted_at`)

계좌(acct_account), 사용자(usr_user), 대출(loan_loan, loan_product)은 법적 보존 의무 또는 참조 무결성을 위해 hard delete 대신 `deleted_at IS NOT NULL`로 비활성화.  
`txn_transaction`은 원장 성격이므로 deleted_at 미적용 (수정/삭제 불가).

---

## 미결 사항 (백엔드 팀 협의 필요)

| # | 항목 | 현재 상태 | 협의 필요 내용 |
|---|---|---|---|
| 1 | `usr_user`와 `acct_account` 연결 | ERD에 user_id FK 추가 | JWT로 필터링하는지, account 테이블에 user_id 컬럼이 있는지 |
| 2 | `account_type` enum 범위 | CHECKING, SAVINGS만 존재 | ISA, CMA 등 추가 타입 여부 |
| 3 | `transaction_type` enum 범위 | DEPOSIT, WITHDRAWAL만 존재 | 이자, 수수료 등 별도 타입 여부 |
| 4 | `TransferSuccess` 응답 스펙 | transferId, status, completedAt만 반환 | 금액·계좌 정보 추가 여부 |
| 5 | `loan_application.repayment_type` 처리 | mock은 무시하고 원리금균등 고정 | 방식별 월 상환액 계산 로직 구현 여부 |
| 6 | 알림 설정 저장 위치 | 현재 프론트 local state만 사용 | 서버 저장 vs localStorage vs DB |
