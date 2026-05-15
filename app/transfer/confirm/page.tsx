"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { useAccounts } from "@/lib/api/hooks";
import { useTransferMutation } from "@/lib/api/transfers";
import { toast } from "@/hooks/use-toast";
import type { TransferFormValues } from "@/lib/schemas/transfer";

export default function ConfirmPage() {
  const router = useRouter();
  // 페이지 진입 시 한 번만 생성 — 버튼 중복 클릭에도 동일 키 사용
  const [idempotencyKey] = useState(() => crypto.randomUUID());
  const [pending, setPending] = useState<TransferFormValues | null>(null);
  const [password, setPassword] = useState("");

  const { data: accounts = [] } = useAccounts();
  const { mutate, isPending } = useTransferMutation();

  useEffect(() => {
    const raw = sessionStorage.getItem("pendingTransfer");
    if (!raw) {
      router.replace("/transfer");
      return;
    }
    setPending(JSON.parse(raw) as TransferFormValues);
  }, [router]);

  if (!pending) return null;

  const fromAccount = accounts.find((a) => a.accountId === pending.fromAccountId);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutate(
      {
        body: {
          fromAccountId: pending.fromAccountId,
          toAccountNo: pending.toAccountNo,
          transferAmount: pending.transferAmount,
          transferMemo: pending.transferMemo,
          transferPassword: password,
        },
        idempotencyKey,
      },
      {
        onSuccess: (data) => {
          sessionStorage.removeItem("pendingTransfer");
          router.push(`/transfer/result?transferId=${data.transferId}`);
        },
        onError: (err) => {
          toast({
            variant: "destructive",
            title: "이체 실패",
            description: err instanceof Error ? err.message : "오류가 발생했습니다.",
          });
        },
      },
    );
  };

  return (
    <main className="min-h-screen bg-gray-50 flex items-start justify-center py-10 px-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>이체 확인</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">

          {/* 이체 정보 요약 */}
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-muted-foreground">출금 계좌</dt>
              <dd className="font-medium text-right">
                {fromAccount
                  ? `${fromAccount.accountNo} (${fromAccount.accountHolder})`
                  : pending.fromAccountId}
              </dd>
            </div>
            <Separator />
            <div className="flex justify-between">
              <dt className="text-muted-foreground">받는 계좌</dt>
              <dd className="font-medium">{pending.toAccountNo}</dd>
            </div>
            <Separator />
            <div className="flex justify-between items-baseline">
              <dt className="text-muted-foreground">이체 금액</dt>
              <dd className="text-lg font-semibold">
                {Number(pending.transferAmount).toLocaleString("ko-KR")}원
              </dd>
            </div>
            {pending.transferMemo && (
              <>
                <Separator />
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">메모</dt>
                  <dd>{pending.transferMemo}</dd>
                </div>
              </>
            )}
          </dl>

          <Separator />

          {/* 비밀번호 + 이체 버튼 */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="password">이체 비밀번호</Label>
              <Input
                id="password"
                type="password"
                inputMode="numeric"
                placeholder="••••"
                maxLength={4}
                value={password}
                onChange={(e) => setPassword(e.target.value.replace(/\D/g, ""))}
                autoComplete="off"
              />
            </div>
            <Button
              type="submit"
              className="w-full"
              disabled={password.length < 4 || isPending}
            >
              {isPending ? "처리 중..." : "이체하기"}
            </Button>
          </form>

        </CardContent>
      </Card>
    </main>
  );
}
