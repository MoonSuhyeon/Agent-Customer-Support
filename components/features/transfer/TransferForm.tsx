"use client";

import { useMemo } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { useAccounts } from "@/lib/api/hooks";
import { createTransferSchema, type TransferFormValues } from "@/lib/schemas/transfer";
import type { Account } from "@/lib/api/types";

function formatAccountNo(value: string): string {
  const digits = value.replace(/\D/g, "").slice(0, 11);
  if (digits.length <= 3) return digits;
  if (digits.length <= 7) return `${digits.slice(0, 3)}-${digits.slice(3)}`;
  return `${digits.slice(0, 3)}-${digits.slice(3, 7)}-${digits.slice(7)}`;
}

interface TransferFormProps {
  defaultFromAccountId?: string;
}

export function TransferForm({ defaultFromAccountId = "" }: TransferFormProps) {
  const router = useRouter();
  const { data: accounts = [], isLoading } = useAccounts();
  const schema = useMemo(() => createTransferSchema(accounts), [accounts]);

  const form = useForm<TransferFormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      fromAccountId: defaultFromAccountId,
      toAccountNo: "",
      transferAmount: "",
      transferMemo: "",
    },
  });

  const onSubmit = (values: TransferFormValues) => {
    sessionStorage.setItem("pendingTransfer", JSON.stringify(values));
    router.push("/transfer/confirm");
  };

  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle>이체</CardTitle>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5">

            {/* 출금 계좌 */}
            <FormField
              control={form.control}
              name="fromAccountId"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>출금 계좌</FormLabel>
                  <Select
                    onValueChange={field.onChange}
                    value={field.value}
                    disabled={isLoading}
                  >
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue
                          placeholder={isLoading ? "불러오는 중..." : "계좌를 선택하세요"}
                        />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {accounts.map((account: Account) => (
                        <SelectItem key={account.accountId} value={account.accountId}>
                          {account.accountNo} · {Number(account.accountBalance).toLocaleString("ko-KR")}원
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* 받는 계좌번호 */}
            <FormField
              control={form.control}
              name="toAccountNo"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>받는 계좌번호</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="000-0000-0000"
                      inputMode="numeric"
                      value={field.value}
                      onChange={(e) => field.onChange(formatAccountNo(e.target.value))}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* 금액 */}
            <FormField
              control={form.control}
              name="transferAmount"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>금액</FormLabel>
                  <div className="relative">
                    <FormControl>
                      <Input
                        placeholder="0"
                        inputMode="numeric"
                        value={
                          field.value
                            ? Number(field.value).toLocaleString("ko-KR")
                            : ""
                        }
                        onChange={(e) => {
                          const raw = e.target.value.replace(/[^0-9]/g, "");
                          field.onChange(raw);
                        }}
                        className="pr-8"
                      />
                    </FormControl>
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground pointer-events-none">
                      원
                    </span>
                  </div>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* 메모 (선택) */}
            <FormField
              control={form.control}
              name="transferMemo"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    메모
                    <span className="ml-1 text-xs text-muted-foreground font-normal">(선택)</span>
                  </FormLabel>
                  <FormControl>
                    <Input placeholder="받는 분에게 표시됩니다" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <Button type="submit" className="w-full">
              다음
            </Button>
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}
