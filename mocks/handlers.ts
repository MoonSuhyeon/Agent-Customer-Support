import { http, HttpResponse } from "msw";
import type { Account, Transaction, TransferRequest, TransferSuccess, ApiError } from "@/lib/api/types";

const MOCK_PASSWORD = "1234";

// ──────────────────────────────────────────────
// 계좌 시드 데이터
// ──────────────────────────────────────────────

const myAccounts: Account[] = [
  {
    accountId: "acc-001",
    accountNo: "110-1234-5678",
    accountHolder: "홍길동",
    accountType: "CHECKING",
    accountBalance: "1000000",
    accountStatus: "ACTIVE",
    openedAt: "2020-03-10T00:00:00Z",
    createdAt: "2020-03-10T00:00:00Z",
  },
  {
    accountId: "acc-002",
    accountNo: "110-9876-5432",
    accountHolder: "홍길동",
    accountType: "CHECKING",
    accountBalance: "500000",
    accountStatus: "ACTIVE",
    openedAt: "2021-07-01T00:00:00Z",
    createdAt: "2021-07-01T00:00:00Z",
  },
  {
    accountId: "acc-003",
    accountNo: "110-1111-2222",
    accountHolder: "홍길동",
    accountType: "SAVINGS",
    accountBalance: "3000000",
    accountStatus: "ACTIVE",
    openedAt: "2022-01-15T00:00:00Z",
    createdAt: "2022-01-15T00:00:00Z",
  },
  {
    accountId: "acc-004",
    accountNo: "110-3333-4444",
    accountHolder: "홍길동",
    accountType: "SAVINGS",
    accountBalance: "1500000",
    accountStatus: "ACTIVE",
    openedAt: "2023-06-20T00:00:00Z",
    createdAt: "2023-06-20T00:00:00Z",
  },
];

const recipientAccounts: Account[] = [
  {
    accountId: "rec-001",
    accountNo: "220-1111-2222",
    accountHolder: "김철수",
    accountType: "CHECKING",
    accountBalance: "2000000",
    accountStatus: "ACTIVE",
    openedAt: "2019-05-01T00:00:00Z",
    createdAt: "2019-05-01T00:00:00Z",
  },
  {
    accountId: "rec-002",
    accountNo: "220-3333-4444",
    accountHolder: "이영희",
    accountType: "CHECKING",
    accountBalance: "1500000",
    accountStatus: "ACTIVE",
    openedAt: "2020-11-20T00:00:00Z",
    createdAt: "2020-11-20T00:00:00Z",
  },
];

const allAccounts = [...myAccounts, ...recipientAccounts];

// ──────────────────────────────────────────────
// 거래 내역 시드 생성
// ──────────────────────────────────────────────

type S = { t: "D" | "W"; a: string; m: string; c: string };

function buildTxns(accountId: string, seeds: S[]): Transaction[] {
  // seeds: 오래된 순 → 최신 순
  // 잔액은 5,000,000 에서 시작해 순차 적용 (데모용, 계좌 잔액과 일치하지 않을 수 있음)
  let balance = 5_000_000n;
  const from = new Date("2024-02-15").getTime();
  const to = new Date("2024-05-15").getTime();
  const step = (to - from) / seeds.length;

  const txns: Transaction[] = seeds.map((s, i) => {
    const amount = BigInt(s.a);
    balance = s.t === "D" ? balance + amount : balance - amount;
    if (balance < 0n) balance = 0n;
    return {
      transactionId: `txn_${accountId}_${String(i + 1).padStart(3, "0")}`,
      accountId,
      transactionType: s.t === "D" ? "DEPOSIT" : "WITHDRAWAL",
      transactionAmount: s.a,
      transactionMemo: s.m,
      counterpartyName: s.c,
      balanceAfter: balance.toString(),
      transactionAt: new Date(from + step * i).toISOString(),
    };
  });

  return txns.reverse(); // 최신 순
}

const acc001Txns = buildTxns("acc-001", [
  { t: "W", a: "500000", m: "월세", c: "부동산중개" },
  { t: "W", a: "90000",  m: "통신비", c: "SKT" },
  { t: "W", a: "80000",  m: "공과금", c: "한국전력" },
  { t: "W", a: "150000", m: "ATM 출금", c: "ATM" },
  { t: "W", a: "40000",  m: "식비", c: "식당" },
  { t: "W", a: "120000", m: "쇼핑", c: "올리브영" },
  { t: "D", a: "200000", m: "이체", c: "이영희" },
  { t: "W", a: "55000",  m: "카페", c: "스타벅스" },
  { t: "W", a: "18000",  m: "편의점", c: "세븐일레븐" },
  { t: "W", a: "300000", m: "병원", c: "서울병원" },
  { t: "D", a: "3500000", m: "월급", c: "ABC주식회사" },
  { t: "W", a: "500000", m: "월세", c: "부동산중개" },
  { t: "W", a: "90000",  m: "통신비", c: "SKT" },
  { t: "W", a: "80000",  m: "공과금", c: "한국전력" },
  { t: "W", a: "25000",  m: "교통비", c: "티머니" },
  { t: "W", a: "30000",  m: "식비", c: "김밥천국" },
  { t: "D", a: "50000",  m: "환불", c: "쿠팡" },
  { t: "W", a: "100000", m: "ATM 출금", c: "ATM" },
  { t: "W", a: "45000",  m: "카페", c: "투썸플레이스" },
  { t: "W", a: "15000",  m: "편의점", c: "CU" },
  { t: "D", a: "3500000", m: "월급", c: "ABC주식회사" },
  { t: "W", a: "500000", m: "월세", c: "부동산중개" },
  { t: "W", a: "80000",  m: "공과금", c: "한국전력" },
  { t: "W", a: "200000", m: "쇼핑", c: "이마트" },
  { t: "W", a: "28000",  m: "식비", c: "맥도날드" },
  { t: "D", a: "100000", m: "이체", c: "김철수" },
  { t: "W", a: "52000",  m: "교통비", c: "카카오T" },
  { t: "W", a: "35000",  m: "식비", c: "식당" },
  { t: "W", a: "12000",  m: "편의점", c: "GS25" },
  { t: "W", a: "48000",  m: "카페", c: "스타벅스" },
]);

const acc002Txns = buildTxns("acc-002", [
  { t: "W", a: "50000",  m: "카페", c: "스타벅스" },
  { t: "W", a: "100000", m: "ATM 출금", c: "ATM" },
  { t: "D", a: "2000000", m: "월급", c: "ABC주식회사" },
  { t: "W", a: "400000", m: "월세", c: "부동산중개" },
  { t: "W", a: "80000",  m: "통신비", c: "KT" },
  { t: "W", a: "90000",  m: "공과금", c: "한국전력" },
  { t: "W", a: "30000",  m: "카페", c: "이디야" },
  { t: "W", a: "200000", m: "쇼핑", c: "이마트" },
  { t: "D", a: "2000000", m: "월급", c: "ABC주식회사" },
  { t: "W", a: "400000", m: "월세", c: "부동산중개" },
  { t: "W", a: "80000",  m: "통신비", c: "KT" },
  { t: "W", a: "100000", m: "ATM 출금", c: "ATM" },
  { t: "W", a: "25000",  m: "편의점", c: "GS25" },
  { t: "W", a: "30000",  m: "식비", c: "식당" },
  { t: "D", a: "2000000", m: "월급", c: "ABC주식회사" },
  { t: "W", a: "400000", m: "월세", c: "부동산중개" },
  { t: "W", a: "80000",  m: "통신비", c: "KT" },
  { t: "W", a: "50000",  m: "식비", c: "한식당" },
  { t: "D", a: "500000", m: "이체", c: "홍길동" },
  { t: "W", a: "15000",  m: "교통비", c: "티머니" },
]);

const acc003Txns = buildTxns("acc-003", [
  { t: "D", a: "500000",  m: "이체", c: "홍길동" },
  { t: "D", a: "1000000", m: "적금 납입", c: "자동이체" },
  { t: "D", a: "500000",  m: "이체", c: "홍길동" },
  { t: "D", a: "1000000", m: "이자 입금", c: "은행" },
  { t: "W", a: "2000000", m: "이체 출금", c: "홍길동" },
  { t: "D", a: "1000000", m: "적금 납입", c: "자동이체" },
  { t: "D", a: "500000",  m: "이체", c: "홍길동" },
  { t: "D", a: "1000000", m: "적금 납입", c: "자동이체" },
  { t: "D", a: "500000",  m: "이체", c: "홍길동" },
  { t: "D", a: "1000000", m: "이자 입금", c: "은행" },
  { t: "D", a: "1000000", m: "적금 납입", c: "자동이체" },
  { t: "D", a: "500000",  m: "이체", c: "홍길동" },
  { t: "D", a: "1000000", m: "적금 납입", c: "자동이체" },
  { t: "D", a: "500000",  m: "이체", c: "홍길동" },
  { t: "D", a: "500000",  m: "이체", c: "홍길동" },
]);

const acc004Txns = buildTxns("acc-004", [
  { t: "D", a: "300000", m: "이체", c: "홍길동" },
  { t: "D", a: "500000", m: "적금 납입", c: "자동이체" },
  { t: "D", a: "300000", m: "이체", c: "홍길동" },
  { t: "D", a: "500000", m: "적금 납입", c: "자동이체" },
  { t: "D", a: "300000", m: "이체", c: "홍길동" },
  { t: "D", a: "500000", m: "이자 입금", c: "은행" },
  { t: "D", a: "300000", m: "이체", c: "홍길동" },
  { t: "D", a: "500000", m: "적금 납입", c: "자동이체" },
  { t: "D", a: "300000", m: "이체", c: "홍길동" },
  { t: "D", a: "500000", m: "적금 납입", c: "자동이체" },
  { t: "D", a: "300000", m: "이체", c: "홍길동" },
  { t: "D", a: "500000", m: "이자 입금", c: "은행" },
  { t: "D", a: "300000", m: "이체", c: "홍길동" },
  { t: "D", a: "500000", m: "적금 납입", c: "자동이체" },
  { t: "D", a: "300000", m: "이체", c: "홍길동" },
]);

const transactionsByAccount: Record<string, Transaction[]> = {
  "acc-001": acc001Txns,
  "acc-002": acc002Txns,
  "acc-003": acc003Txns,
  "acc-004": acc004Txns,
};

// ──────────────────────────────────────────────
// 이체 상태
// ──────────────────────────────────────────────

const idempotencyCache = new Map<string, { status: number; body: TransferSuccess | ApiError }>();
let transferSeq = 1;

// ──────────────────────────────────────────────
// 핸들러
// ──────────────────────────────────────────────

export const handlers = [
  // GET /api/accounts
  http.get("/api/accounts", () => {
    return HttpResponse.json(myAccounts);
  }),

  // GET /api/accounts/:accountId
  http.get("/api/accounts/:accountId", ({ params }) => {
    const account = allAccounts.find((a) => a.accountId === params.accountId);
    if (!account) {
      return HttpResponse.json(
        { error: { code: "ACCOUNT_NOT_FOUND", message: "계좌를 찾을 수 없습니다." } },
        { status: 404 },
      );
    }
    return HttpResponse.json(account);
  }),

  // GET /api/accounts/:accountId/transactions
  http.get("/api/accounts/:accountId/transactions", ({ params, request }) => {
    const { accountId } = params as { accountId: string };
    const account = allAccounts.find((a) => a.accountId === accountId);
    if (!account) {
      return HttpResponse.json(
        { error: { code: "ACCOUNT_NOT_FOUND", message: "계좌를 찾을 수 없습니다." } },
        { status: 404 },
      );
    }

    const url = new URL(request.url);
    const page = Math.max(1, Number(url.searchParams.get("page") ?? "1"));
    const size = Math.max(1, Number(url.searchParams.get("size") ?? "20"));
    const type = url.searchParams.get("type") ?? "ALL";

    const all = transactionsByAccount[accountId] ?? [];
    const filtered =
      type === "ALL" ? all : all.filter((t) => t.transactionType === type);

    const start = (page - 1) * size;
    const content = filtered.slice(start, start + size);

    return HttpResponse.json({
      content,
      totalElements: filtered.length,
      totalPages: Math.ceil(filtered.length / size),
      currentPage: page,
      size,
    });
  }),

  // POST /api/transfers
  http.post("/api/transfers", async ({ request }) => {
    const idempotencyKey = request.headers.get("Idempotency-Key");

    if (idempotencyKey && idempotencyCache.has(idempotencyKey)) {
      const cached = idempotencyCache.get(idempotencyKey)!;
      return HttpResponse.json(cached.body, { status: cached.status });
    }

    const body = (await request.json()) as TransferRequest;

    const respond = (status: number, responseBody: TransferSuccess | ApiError) => {
      if (idempotencyKey) idempotencyCache.set(idempotencyKey, { status, body: responseBody });
      return HttpResponse.json(responseBody, { status });
    };

    if (body.transferPassword !== MOCK_PASSWORD) {
      return respond(400, { error: { code: "INVALID_PASSWORD", message: "비밀번호가 올바르지 않습니다." } });
    }

    const fromAccount = myAccounts.find((a) => a.accountId === body.fromAccountId);
    if (!fromAccount) {
      return respond(404, { error: { code: "ACCOUNT_NOT_FOUND", message: "출금 계좌를 찾을 수 없습니다." } });
    }

    const toAccount = allAccounts.find((a) => a.accountNo === body.toAccountNo);
    if (!toAccount) {
      return respond(404, { error: { code: "ACCOUNT_NOT_FOUND", message: "입금 계좌를 찾을 수 없습니다." } });
    }

    const balance = BigInt(fromAccount.accountBalance);
    const amount = BigInt(body.transferAmount);

    if (balance < amount) {
      return respond(422, { error: { code: "INSUFFICIENT_BALANCE", message: "잔액이 부족합니다." } });
    }

    fromAccount.accountBalance = (balance - amount).toString();

    return respond(200, {
      transferId: `TXN-${String(transferSeq++).padStart(6, "0")}`,
      transferStatus: "COMPLETED",
      completedAt: new Date().toISOString(),
    });
  }),
];
