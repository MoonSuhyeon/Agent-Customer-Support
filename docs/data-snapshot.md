# 사이트 데이터 스냅샷

> 이 문서는 프로젝트의 mock 데이터를 정리한 것으로, ERD 설계의 기반 자료다.  
> 소스: `mocks/handlers.ts`, `lib/api/types.ts`, `lib/api/settings.ts`, `lib/schemas/transfer.ts`  
> 데이터 변경 시 재생성 필요.

---

## 개요

| 엔티티 | 레코드 수 | 사용 화면 |
|---|---|---|
| UserProfile | 1 | 설정 > 프로필, 헤더 사용자명 |
| Account | 6 (내 계좌 4 + 상대방 2) | 대시보드, 내 계좌, 계좌 상세, 이체 |
| Transaction | 79 (acc-001:30, acc-002:19, acc-003:15, acc-004:15) | 계좌 상세, 거래 내역, 대시보드 최근 거래 |
| Transfer | 요청/응답 구조만 (저장 안 됨) | 이체 입력, 확인, 결과 |
| LoanProduct | 4 | 대출 > 상품 목록, 신청 폼 |
| Loan (내 대출) | 1 | 대출 > 현황 |
| LoanApplication | 응답 구조만 (저장 안 됨) | 대출 신청 결과 |

---

## 1. UserProfile (사용자)

### TypeScript 타입
```typescript
// lib/api/settings.ts
interface UserProfile {
  name: string;
  email: string;
  phone: string;
}
```

> ⚠️ userId, passwordHash 등 인증 관련 필드가 타입에 없음. 현재 mock은 인증 없이 동작.

### 실제 데이터 (전체)
```json
{
  "name": "홍길동",
  "email": "hong@example.com",
  "phone": "010-1234-5678"
}
```

### 필드 설명
| 필드 | 의미 | 자료형 | 비고 |
|---|---|---|---|
| name | 이름 | string | 읽기 전용 (수정 불가) |
| email | 이메일 | string | 수정 가능 |
| phone | 전화번호 | string | 형식: `010-XXXX-XXXX` |

### Mock 비밀번호
| 용도 | 값 | 검증 위치 |
|---|---|---|
| 로그인 비밀번호 (변경 시 현재 비밀번호 확인) | `"1234"` | `PATCH /api/user/password` |
| 이체 비밀번호 | `"1234"` | `POST /api/transfers`, `PATCH /api/user/transfer-password` |

---

## 2. Account (계좌)

### TypeScript 타입
```typescript
// lib/api/types.ts
interface Account {
  accountId: string;
  accountNo: string;
  accountHolder: string;
  accountType: "CHECKING" | "SAVINGS";
  accountBalance: string; // 원 단위 정수, string 직렬화
  accountStatus: "ACTIVE" | "INACTIVE" | "SUSPENDED";
  openedAt: string;  // ISO 8601
  createdAt: string; // ISO 8601
}
```

### 실제 데이터 — 내 계좌 (myAccounts)
```json
[
  {
    "accountId": "acc-001",
    "accountNo": "110-1234-5678",
    "accountHolder": "홍길동",
    "accountType": "CHECKING",
    "accountBalance": "1000000",
    "accountStatus": "ACTIVE",
    "openedAt": "2020-03-10T00:00:00Z",
    "createdAt": "2020-03-10T00:00:00Z"
  },
  {
    "accountId": "acc-002",
    "accountNo": "110-9876-5432",
    "accountHolder": "홍길동",
    "accountType": "CHECKING",
    "accountBalance": "500000",
    "accountStatus": "ACTIVE",
    "openedAt": "2021-07-01T00:00:00Z",
    "createdAt": "2021-07-01T00:00:00Z"
  },
  {
    "accountId": "acc-003",
    "accountNo": "110-1111-2222",
    "accountHolder": "홍길동",
    "accountType": "SAVINGS",
    "accountBalance": "3000000",
    "accountStatus": "ACTIVE",
    "openedAt": "2022-01-15T00:00:00Z",
    "createdAt": "2022-01-15T00:00:00Z"
  },
  {
    "accountId": "acc-004",
    "accountNo": "110-3333-4444",
    "accountHolder": "홍길동",
    "accountType": "SAVINGS",
    "accountBalance": "1500000",
    "accountStatus": "ACTIVE",
    "openedAt": "2023-06-20T00:00:00Z",
    "createdAt": "2023-06-20T00:00:00Z"
  }
]
```

### 실제 데이터 — 상대방 계좌 (recipientAccounts)
```json
[
  {
    "accountId": "rec-001",
    "accountNo": "220-1111-2222",
    "accountHolder": "김철수",
    "accountType": "CHECKING",
    "accountBalance": "2000000",
    "accountStatus": "ACTIVE",
    "openedAt": "2019-05-01T00:00:00Z",
    "createdAt": "2019-05-01T00:00:00Z"
  },
  {
    "accountId": "rec-002",
    "accountNo": "220-3333-4444",
    "accountHolder": "이영희",
    "accountType": "CHECKING",
    "accountBalance": "1500000",
    "accountStatus": "ACTIVE",
    "openedAt": "2020-11-20T00:00:00Z",
    "createdAt": "2020-11-20T00:00:00Z"
  }
]
```

> ⚠️ myAccounts와 recipientAccounts가 코드에서 별도 배열로 분리됨.  
> `GET /api/accounts`는 myAccounts만 반환. 이체 시 수신 계좌 조회는 accountNo로 allAccounts에서 탐색.

### 필드 설명
| 필드 | 의미 | 자료형 | 비고 |
|---|---|---|---|
| accountId | 계좌 고유 ID | string | PK 후보 |
| accountNo | 계좌번호 | string | 형식: `XXX-XXXX-XXXX`, unique 추정 |
| accountHolder | 예금주명 | string | User.name과 동일값 사용 (FK 아님) |
| accountType | 계좌 유형 | `"CHECKING"` \| `"SAVINGS"` | 보통예금 \| 저축예금 |
| accountBalance | 잔액 | string | 원 단위 정수를 string으로 직렬화. 이체 시 실시간 갱신됨 |
| accountStatus | 계좌 상태 | `"ACTIVE"` \| `"INACTIVE"` \| `"SUSPENDED"` | mock에는 전부 ACTIVE |
| openedAt | 개설일 | string (ISO 8601) | |
| createdAt | 레코드 생성일 | string (ISO 8601) | mock에서 openedAt과 동일값 |

---

## 3. Transaction (거래 내역)

### TypeScript 타입
```typescript
// lib/api/types.ts
interface Transaction {
  transactionId: string;
  accountId: string;
  transactionType: "DEPOSIT" | "WITHDRAWAL";
  transactionAmount: string; // 원 단위 정수, string 직렬화
  transactionMemo: string;
  counterpartyName: string;
  balanceAfter: string; // 거래 후 잔액
  transactionAt: string; // ISO 8601
}

interface PagedTransactions {
  content: Transaction[];
  totalElements: number;
  totalPages: number;
  currentPage: number;
  size: number;
}

type TransactionType = "ALL" | "DEPOSIT" | "WITHDRAWAL";
```

### 실제 데이터 샘플 (acc-001 중 3개, 최신순)
```json
[
  {
    "transactionId": "txn_acc-001_030",
    "accountId": "acc-001",
    "transactionType": "WITHDRAWAL",
    "transactionAmount": "48000",
    "transactionMemo": "카페",
    "counterpartyName": "스타벅스",
    "balanceAfter": "계산값",
    "transactionAt": "2024-05-14T..."
  },
  {
    "transactionId": "txn_acc-001_029",
    "accountId": "acc-001",
    "transactionType": "WITHDRAWAL",
    "transactionAmount": "12000",
    "transactionMemo": "편의점",
    "counterpartyName": "GS25",
    "balanceAfter": "계산값",
    "transactionAt": "2024-05-11T..."
  },
  {
    "transactionId": "txn_acc-001_011",
    "accountId": "acc-001",
    "transactionType": "DEPOSIT",
    "transactionAmount": "3500000",
    "transactionMemo": "월급",
    "counterpartyName": "ABC주식회사",
    "balanceAfter": "계산값",
    "transactionAt": "2024-03-29T..."
  }
]
```

> `balanceAfter`와 `transactionAt`은 시드 데이터에서 계산 생성됨 (`buildTxns` 함수).  
> 기준 잔액 5,000,000원에서 순차 적용. 실제 계좌 잔액(accountBalance)과 일치하지 않음 (데모용).  
> 날짜 범위: 2024-02-15 ~ 2024-05-15.

### 필드 설명
| 필드 | 의미 | 자료형 | 비고 |
|---|---|---|---|
| transactionId | 거래 고유 ID | string | 형식: `txn_{accountId}_{순번}` |
| accountId | 계좌 ID | string | Account.accountId 참조 (FK) |
| transactionType | 거래 유형 | `"DEPOSIT"` \| `"WITHDRAWAL"` | 입금 \| 출금 |
| transactionAmount | 거래 금액 | string | 원 단위 정수, string 직렬화 |
| transactionMemo | 메모 | string | 예: "월세", "월급", "ATM 출금" |
| counterpartyName | 거래 상대방 | string | 예: "ABC주식회사", "스타벅스" (추정: 단순 문자열) |
| balanceAfter | 거래 후 잔액 | string | 원 단위 정수, string 직렬화 |
| transactionAt | 거래 일시 | string (ISO 8601) | |

---

## 4. Transfer (이체)

### TypeScript 타입
```typescript
// lib/api/types.ts
interface TransferRequest {
  fromAccountId: string;
  toAccountNo: string;    // accountId가 아닌 accountNo 사용
  transferAmount: string;
  transferMemo: string;
  transferPassword: string;
}

interface TransferSuccess {
  transferId: string;
  transferStatus: "COMPLETED";
  completedAt: string; // ISO 8601
}

interface ApiError {
  error: {
    code: string;
    message: string;
  };
}
```

### 이체 흐름 데이터
```
1. 사용자 입력 → TransferFormValues (sessionStorage 임시 저장)
   { fromAccountId, toAccountNo, transferAmount, transferMemo }

2. 확인 페이지 → TransferRequest (API 전송)
   위 + transferPassword 추가

3. 성공 응답 → TransferSuccess
   { transferId: "TXN-000001", transferStatus: "COMPLETED", completedAt: "..." }
```

### 에러 코드 목록 (mock 기준)
| code | 발생 조건 |
|---|---|
| `INVALID_PASSWORD` | 이체 비밀번호 불일치 |
| `ACCOUNT_NOT_FOUND` | 출금/입금 계좌 없음 |
| `INSUFFICIENT_BALANCE` | 잔액 부족 |

### 필드 설명 (TransferRequest)
| 필드 | 의미 | 자료형 | 비고 |
|---|---|---|---|
| fromAccountId | 출금 계좌 ID | string | Account.accountId 참조 |
| toAccountNo | 입금 계좌번호 | string | Account.accountNo 참조 (ID 아님) |
| transferAmount | 이체 금액 | string | 원 단위 정수, string 직렬화. 최소 1원 |
| transferMemo | 메모 | string | 선택 입력 |
| transferPassword | 이체 비밀번호 | string | 4자리 숫자 |

> ⚠️ TransferSuccess에 금액, 계좌 정보가 없음. 결과 화면에서 transferId만 표시 가능.

---

## 5. LoanProduct (대출 상품)

### TypeScript 타입
```typescript
// lib/api/types.ts
interface LoanProduct {
  productId: string;
  productName: string;
  description: string;
  maxAmount: string; // 원 단위 정수, string 직렬화
  minRate: number;   // 연이율 (%)
  maxRate: number;   // 연이율 (%)
}
```

### 실제 데이터 (전체)
```json
[
  {
    "productId": "prod-001",
    "productName": "신용대출",
    "description": "신용 등급 기반의 간편 비대면 대출",
    "maxAmount": "50000000",
    "minRate": 3.5,
    "maxRate": 8.5
  },
  {
    "productId": "prod-002",
    "productName": "주택담보대출",
    "description": "주택을 담보로 한 장기 저금리 대출",
    "maxAmount": "500000000",
    "minRate": 2.8,
    "maxRate": 5.5
  },
  {
    "productId": "prod-003",
    "productName": "자동차담보대출",
    "description": "차량을 담보로 한 중금리 실시간 대출",
    "maxAmount": "80000000",
    "minRate": 4.5,
    "maxRate": 9.0
  },
  {
    "productId": "prod-004",
    "productName": "비상금대출",
    "description": "급할 때 즉시 받는 소액 한도 대출",
    "maxAmount": "3000000",
    "minRate": 6.5,
    "maxRate": 15.0
  }
]
```

### 필드 설명
| 필드 | 의미 | 자료형 | 비고 |
|---|---|---|---|
| productId | 상품 고유 ID | string | PK 후보 |
| productName | 상품명 | string | |
| description | 한 줄 설명 | string | |
| maxAmount | 최대 대출 한도 | string | 원 단위 정수, string 직렬화 |
| minRate | 최저 금리 | number | 연이율 (%), 소수점 1자리 |
| maxRate | 최고 금리 | number | 연이율 (%), 소수점 1자리 |

---

## 6. Loan (내 대출)

### TypeScript 타입
```typescript
// lib/api/types.ts
interface MyLoan {
  loanId: string;
  productName: string;   // productId가 아닌 이름 문자열
  principalAmount: string;
  remainingAmount: string;
  nextPaymentDate: string; // YYYY-MM-DD
  interestRate: number;    // 연이율 (%)
  monthlyPayment: string;
  status: "ACTIVE" | "COMPLETED";
}
```

### 실제 데이터 (전체)
```json
[
  {
    "loanId": "loan-001",
    "productName": "신용대출",
    "principalAmount": "20000000",
    "remainingAmount": "15000000",
    "nextPaymentDate": "2026-06-15",
    "interestRate": 4.2,
    "monthlyPayment": "370000",
    "status": "ACTIVE"
  }
]
```

### 필드 설명
| 필드 | 의미 | 자료형 | 비고 |
|---|---|---|---|
| loanId | 대출 고유 ID | string | PK 후보 |
| productName | 대출 상품명 | string | LoanProduct.productName 값 (FK 아님, 문자열) |
| principalAmount | 대출 원금 | string | 원 단위 정수, string 직렬화 |
| remainingAmount | 잔여 원금 | string | 원 단위 정수, string 직렬화 |
| nextPaymentDate | 다음 상환일 | string | 형식: `YYYY-MM-DD` |
| interestRate | 적용 금리 | number | 연이율 (%) |
| monthlyPayment | 월 상환액 | string | 원 단위 정수, string 직렬화 |
| status | 대출 상태 | `"ACTIVE"` \| `"COMPLETED"` | |

---

## 7. LoanApplication (대출 신청 결과)

> 별도 저장 없음. `POST /api/loans/apply` 응답으로만 존재 (멱등성 캐시에 일시 보관).

### TypeScript 타입
```typescript
// lib/api/types.ts
interface LoanApplyRequest {
  productId: string;
  amount: string;
  termMonths: number;
  repaymentType: string; // "EQUAL_INSTALLMENT" | "EQUAL_PRINCIPAL" | "BALLOON"
  reason?: string;
}

interface LoanApplyResult {
  applicationId: string;
  status: "APPROVED";
  approvedAmount: string;
  interestRate: number;
  monthlyPayment: string;
  termMonths: number;
  productName: string;
  approvedAt: string; // ISO 8601
}
```

### 응답 예시
```json
{
  "applicationId": "APP-000001",
  "status": "APPROVED",
  "approvedAmount": "10000000",
  "interestRate": 6.0,
  "monthlyPayment": "193000",
  "termMonths": 60,
  "productName": "신용대출",
  "approvedAt": "2026-05-15T12:00:00.000Z"
}
```

> mock은 항상 APPROVED 반환. 금리는 상품의 (minRate + maxRate) / 2.  
> 월 상환액은 원리금균등 공식으로 계산 (repaymentType 무시).

---

## 데이터 관계 추정

```
UserProfile ──── Account
  (1)              (N)
  근거: 없음. accountHolder가 user name과 같은 문자열을 쓰지만
        Account에 userId FK 필드가 없음. (추정: 실제 API에는 있을 것)

Account ──────── Transaction
  (1)                (N)
  근거: Transaction.accountId → Account.accountId 직접 참조

Account ──────── Transfer (출금 측)
  (1)                (N)
  근거: TransferRequest.fromAccountId → Account.accountId

Account ──────── Transfer (입금 측)
  (1)                (N)
  근거: TransferRequest.toAccountNo → Account.accountNo
        ※ ID가 아닌 accountNo로 참조 — 외부 은행 계좌도 수용하기 위한 설계 추정

LoanProduct ──── Loan
  (1)              (N)
  근거: 느슨한 연결. Loan.productName이 LoanProduct.productName과 같은 문자열
        productId FK가 없음

UserProfile ──── Loan
  (1)              (N)
  근거: 없음. GET /api/loans/my가 로그인 사용자 기준으로 반환한다고 추정
```

---

## 의문점 / 결정 필요 사항

백엔드 팀과 협의가 필요한 항목:

1. **Account ↔ User 연결 방식**  
   현재 Account에 userId(소유자) FK가 없음. 실제 API에서는 JWT 토큰으로 소유자를 필터링하는지, 아니면 Account에 userId 필드가 있는지 확인 필요.

2. **counterpartyName의 정체**  
   거래 상대방 이름이 단순 문자열인지, 별도 Contact/Account 테이블을 참조하는 FK인지 불명확. 현재 mock은 그냥 문자열.

3. **TransferSuccess 응답 필드 부족**  
   성공 응답에 금액, 계좌 정보가 없음. 결과 화면에서 transferId만 보여줄 수 있음. 실제 API에서 추가 필드(amount, fromAccountNo 등)를 줄 것인지 확인 필요.

4. **toAccountNo vs toAccountId**  
   이체 시 입금 계좌를 `accountNo`(계좌번호 문자열)로 참조. 외부 은행 계좌 수용을 위한 의도적 설계인지, 내부적으로는 accountId로 변환되는지 확인 필요.

5. **Loan ↔ LoanProduct 연결 방식**  
   Loan.productName이 문자열. 실제 DB에서는 productId FK를 쓸지, 상품 정보를 Loan에 denormalize할지 결정 필요.

6. **accountType enum 범위**  
   mock에는 `CHECKING`, `SAVINGS`만 존재. 실제로 더 있는지 (예: `ISA`, `CMA`) 확인 필요.

7. **transactionType enum 범위**  
   현재 `DEPOSIT`, `WITHDRAWAL`만 있음. 이체 수수료, 이자 입금 등 별도 타입이 생길지 확인 필요.

8. **LoanApplyRequest.repaymentType**  
   mock이 repaymentType을 무시하고 항상 원리금균등으로 계산. 실제 API에서 각 방식별 월 상환액 계산 로직이 다를 것. 타입도 현재 `string`으로 느슨하게 정의됨.

9. **Notification, Setting 엔티티**  
   설정 페이지에 알림 토글, 다크모드 등이 있지만 API가 없음 (로컬 state만 사용). 실제 서버에 저장할지, localStorage에서 관리할지 결정 필요.
