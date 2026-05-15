import { apiClient } from "./client";
import type { LoanProduct, MyLoan, LoanApplyRequest, LoanApplyResult } from "./types";

export function getLoanProducts(): Promise<LoanProduct[]> {
  return apiClient.get<LoanProduct[]>("/loans/products");
}

export function getMyLoans(): Promise<MyLoan[]> {
  return apiClient.get<MyLoan[]>("/loans/my");
}

export function applyLoan(body: LoanApplyRequest, idempotencyKey: string): Promise<LoanApplyResult> {
  return apiClient.post<LoanApplyResult>("/loans/apply", body, {
    headers: { "Idempotency-Key": idempotencyKey },
  });
}
