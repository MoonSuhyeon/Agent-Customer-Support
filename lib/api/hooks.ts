import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getAccounts, getAccount, getTransactions, type TransactionParams } from "./accounts";
import { getProfile, updateProfile, changePassword, changeTransferPassword } from "./settings";
import { getLoanProducts, getMyLoans, applyLoan } from "./loans";
import type { LoanApplyRequest } from "./types";

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

export function useProfile() {
  return useQuery({
    queryKey: ["user", "profile"],
    queryFn: getProfile,
  });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: updateProfile,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["user", "profile"] }),
  });
}

export function useChangePassword() {
  return useMutation({ mutationFn: changePassword });
}

export function useChangeTransferPassword() {
  return useMutation({ mutationFn: changeTransferPassword });
}

export function useLoanProducts() {
  return useQuery({
    queryKey: ["loans", "products"],
    queryFn: getLoanProducts,
  });
}

export function useMyLoans() {
  return useQuery({
    queryKey: ["loans", "my"],
    queryFn: getMyLoans,
  });
}

export function useApplyLoan() {
  return useMutation({
    mutationFn: ({ body, idempotencyKey }: { body: LoanApplyRequest; idempotencyKey: string }) =>
      applyLoan(body, idempotencyKey),
  });
}
