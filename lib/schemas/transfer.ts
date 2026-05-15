import { z } from "zod";
import type { Account } from "@/lib/api/types";

export interface TransferFormValues {
  fromAccountId: string;
  toAccountNo: string;
  transferAmount: string; // raw integer string, 콤마 없음
  transferMemo: string;
}

export const createTransferSchema = (accounts: Account[]) =>
  z
    .object({
      fromAccountId: z.string().min(1, "출금 계좌를 선택해주세요."),
      toAccountNo: z
        .string()
        .min(1, "받는 계좌번호를 입력해주세요.")
        .regex(/^\d{3}-\d{4}-\d{4}$/, "올바른 계좌번호 형식이 아닙니다."),
      transferAmount: z
        .string()
        .min(1, "금액을 입력해주세요.")
        .refine((v) => /^\d+$/.test(v) && BigInt(v) >= 1n, "1원 이상 입력해주세요."),
      transferMemo: z.string(),
    })
    .superRefine((data, ctx) => {
      const from = accounts.find((a) => a.accountId === data.fromAccountId);
      if (!from) return;

      if (from.accountNo === data.toAccountNo) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["toAccountNo"],
          message: "출금 계좌와 동일한 계좌로는 이체할 수 없습니다.",
        });
      }

      if (/^\d+$/.test(data.transferAmount)) {
        const amount = BigInt(data.transferAmount);
        const balance = BigInt(from.accountBalance);
        if (amount > balance) {
          ctx.addIssue({
            code: z.ZodIssueCode.custom,
            path: ["transferAmount"],
            message: `잔액 초과 (잔액: ${Number(from.accountBalance).toLocaleString("ko-KR")}원)`,
          });
        }
      }
    });
