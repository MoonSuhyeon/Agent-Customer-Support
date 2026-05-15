import { apiClient } from "./client";
import type { Account, PagedTransactions, TransactionType } from "./types";

export const getAccounts = () => apiClient.get<Account[]>("/accounts");

export const getAccount = (accountId: string) =>
  apiClient.get<Account>(`/accounts/${accountId}`);

export interface TransactionParams {
  page?: number;
  size?: number;
  type?: TransactionType;
}

export const getTransactions = (accountId: string, params: TransactionParams = {}) => {
  const qs = new URLSearchParams({
    page: String(params.page ?? 1),
    size: String(params.size ?? 20),
    type: params.type ?? "ALL",
  });
  return apiClient.get<PagedTransactions>(`/accounts/${accountId}/transactions?${qs}`);
};
