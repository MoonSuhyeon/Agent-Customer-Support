import { z } from "zod";

export const loanApplySchema = z.object({
  productId: z.string().min(1, "대출 상품을 선택해주세요."),
  amount: z
    .string()
    .min(1, "금액을 입력해주세요.")
    .refine(
      (v) => {
        const n = Number(v.replace(/,/g, ""));
        return !isNaN(n) && n >= 1_000_000;
      },
      "최소 100만원 이상 신청 가능합니다.",
    ),
  termMonths: z.string().min(1, "대출 기간을 선택해주세요."),
  repaymentType: z.string().min(1, "상환 방식을 선택해주세요."),
  reason: z.string().optional(),
});

export type LoanApplyFormValues = z.infer<typeof loanApplySchema>;
