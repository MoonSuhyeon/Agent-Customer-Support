"use client";

import { useRef } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { toast } from "@/hooks/use-toast";
import { useLoanProducts, useApplyLoan } from "@/lib/api/hooks";
import { loanApplySchema, type LoanApplyFormValues } from "@/lib/schemas/loans";

const TERM_OPTIONS = [
  { value: "12", label: "12개월" },
  { value: "24", label: "24개월" },
  { value: "36", label: "36개월" },
  { value: "60", label: "60개월" },
];

const REPAYMENT_OPTIONS = [
  { value: "EQUAL_INSTALLMENT", label: "원리금균등" },
  { value: "EQUAL_PRINCIPAL", label: "원금균등" },
  { value: "BALLOON", label: "만기일시" },
];

interface Props {
  initialProductId?: string;
}

export function LoanApplyForm({ initialProductId }: Props) {
  const router = useRouter();
  const { data: products = [], isLoading } = useLoanProducts();
  const { mutateAsync, isPending } = useApplyLoan();
  const idempotencyKey = useRef(crypto.randomUUID());

  const form = useForm<LoanApplyFormValues>({
    resolver: zodResolver(loanApplySchema),
    defaultValues: {
      productId: initialProductId ?? "",
      amount: "",
      termMonths: "",
      repaymentType: "",
      reason: "",
    },
  });

  const handleAmountChange = (raw: string, onChange: (v: string) => void) => {
    const digits = raw.replace(/[^0-9]/g, "");
    const formatted = digits ? Number(digits).toLocaleString("ko-KR") : "";
    onChange(formatted);
  };

  const onSubmit = async (values: LoanApplyFormValues) => {
    try {
      const result = await mutateAsync({
        body: {
          productId: values.productId,
          amount: values.amount.replace(/,/g, ""),
          termMonths: Number(values.termMonths),
          repaymentType: values.repaymentType,
          reason: values.reason,
        },
        idempotencyKey: idempotencyKey.current,
      });

      const params = new URLSearchParams({
        id: result.applicationId,
        product: result.productName,
        amount: result.approvedAmount,
        rate: String(result.interestRate),
        monthly: result.monthlyPayment,
        term: String(result.termMonths),
      });
      router.push(`/loans/apply/result?${params}`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "다시 시도해주세요.";
      toast({ title: "신청 실패", description: msg, variant: "destructive" });
    }
  };

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
        <FormField
          control={form.control}
          name="productId"
          render={({ field }) => (
            <FormItem>
              <FormLabel>대출 상품</FormLabel>
              <Select
                value={field.value}
                onValueChange={field.onChange}
                disabled={isLoading}
              >
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder="상품을 선택해주세요" />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {products.map((p) => (
                    <SelectItem key={p.productId} value={p.productId}>
                      {p.productName}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="amount"
          render={({ field }) => (
            <FormItem>
              <FormLabel>신청 금액</FormLabel>
              <FormControl>
                <div className="relative">
                  <Input
                    inputMode="numeric"
                    placeholder="1,000,000"
                    value={field.value}
                    onChange={(e) => handleAmountChange(e.target.value, field.onChange)}
                  />
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">
                    원
                  </span>
                </div>
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="termMonths"
          render={({ field }) => (
            <FormItem>
              <FormLabel>대출 기간</FormLabel>
              <Select value={field.value} onValueChange={field.onChange}>
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder="기간을 선택해주세요" />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {TERM_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={o.value}>
                      {o.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="repaymentType"
          render={({ field }) => (
            <FormItem>
              <FormLabel>상환 방식</FormLabel>
              <Select value={field.value} onValueChange={field.onChange}>
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder="상환 방식을 선택해주세요" />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {REPAYMENT_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={o.value}>
                      {o.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="reason"
          render={({ field }) => (
            <FormItem>
              <FormLabel>
                신청 사유{" "}
                <span className="text-muted-foreground font-normal">(선택)</span>
              </FormLabel>
              <FormControl>
                <Textarea
                  placeholder="대출 신청 사유를 입력해주세요"
                  className="resize-none"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <Button type="submit" className="w-full" disabled={isPending}>
          {isPending ? "신청 중..." : "신청하기"}
        </Button>
      </form>
    </Form>
  );
}
