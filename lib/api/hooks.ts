import { useQuery } from "@tanstack/react-query";
import { getAccounts, getAccount, getTransactions, type TransactionParams } from "./accounts";

export function useAccounts() {
  return useQuery({
    queryKey: ["accounts"],
    queryFn: getAccounts,
  });
}

export function useAccount(accountId: string) {
  return useQuery({
    queryKey: ["accounts", accountId],
    queryFn: () => getAccount(accountId),
    enabled: !!accountId,
  });
}

export function useTransactions(accountId: string, params: TransactionParams = {}) {
  return useQuery({
    queryKey: ["accounts", accountId, "transactions", params],
    queryFn: () => getTransactions(accountId, params),
    enabled: !!accountId,
  });
}
