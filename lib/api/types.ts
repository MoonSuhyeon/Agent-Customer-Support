export interface Account {
  accountId: string;
  accountNo: string;
  accountHolder: string;
  accountType: "CHECKING" | "SAVINGS";
  accountBalance: string; // 원 단위 정수, string 직렬화
  accountStatus: "ACTIVE" | "INACTIVE" | "SUSPENDED";
  openedAt: string; // ISO 8601
  createdAt: string; // ISO 8601
}

export interface Transaction {
  transactionId: string;
  accountId: string;
  transactionType: "DEPOSIT" | "WITHDRAWAL";
  transactionAmount: string; // 원 단위 정수, string 직렬화
  transactionMemo: string;
  counterpartyName: string;
  balanceAfter: string; // 거래 후 잔액
  transactionAt: string; // ISO 8601
}

export interface PagedTransactions {
  content: Transaction[];
  totalElements: number;
  totalPages: number;
  currentPage: number;
  size: number;
}

export type TransactionType = "ALL" | "DEPOSIT" | "WITHDRAWAL";

export interface TransferRequest {
  fromAccountId: string;
  toAccountNo: string;
  transferAmount: string;
  transferMemo: string;
  transferPassword: string;
}

export interface TransferSuccess {
  transferId: string;
  transferStatus: "COMPLETED";
  completedAt: string;
}

export interface ApiError {
  error: {
    code: string;
    message: string;
  };
}

export type TransferResponse = TransferSuccess | ApiError;
