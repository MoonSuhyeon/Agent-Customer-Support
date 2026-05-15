import { useMutation } from "@tanstack/react-query";
import { apiClient } from "./client";
import type { TransferRequest, TransferSuccess } from "./types";

export function useTransferMutation() {
  return useMutation({
    mutationFn: ({
      body,
      idempotencyKey,
    }: {
      body: TransferRequest;
      idempotencyKey: string;
    }) =>
      apiClient.post<TransferSuccess>("/transfers", body, {
        headers: {
          "Idempotency-Key": idempotencyKey,
          Authorization: "Bearer mock-token",
        },
      }),
  });
}
