import { z } from "zod";

export const profileSchema = z.object({
  email: z.string().email("올바른 이메일 형식이 아닙니다."),
  phone: z
    .string()
    .min(1, "전화번호를 입력해주세요.")
    .regex(/^010-\d{4}-\d{4}$/, "올바른 형식으로 입력해주세요. (010-0000-0000)"),
});

export type ProfileFormValues = z.infer<typeof profileSchema>;

export const passwordSchema = z
  .object({
    current: z.string().min(1, "현재 비밀번호를 입력해주세요."),
    next: z.string().min(8, "비밀번호는 8자 이상이어야 합니다."),
    confirm: z.string().min(1, "비밀번호 확인을 입력해주세요."),
  })
  .refine((d) => d.next === d.confirm, {
    message: "새 비밀번호가 일치하지 않습니다.",
    path: ["confirm"],
  });

export type PasswordFormValues = z.infer<typeof passwordSchema>;

export const transferPasswordSchema = z
  .object({
    current: z
      .string()
      .length(4, "이체 비밀번호는 4자리입니다.")
      .regex(/^\d{4}$/, "숫자 4자리를 입력해주세요."),
    next: z
      .string()
      .length(4, "이체 비밀번호는 4자리입니다.")
      .regex(/^\d{4}$/, "숫자 4자리를 입력해주세요."),
    confirm: z.string().length(4, "이체 비밀번호는 4자리입니다."),
  })
  .refine((d) => d.next === d.confirm, {
    message: "새 비밀번호가 일치하지 않습니다.",
    path: ["confirm"],
  });

export type TransferPasswordFormValues = z.infer<typeof transferPasswordSchema>;
