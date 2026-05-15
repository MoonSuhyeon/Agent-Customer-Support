"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import { HttpError } from "@/lib/api/client";
import { useAccount, useTransactions } from "@/lib/api/hooks";
import { AccountDetailCard } from "@/components/features/account/AccountDetailCard";
import { TransactionList } from "@/components/features/transaction/TransactionList";
import { Button } from "@/components/ui/button";

export default function AccountDetailPage() {
  const { accountId } = useParams<{ accountId: string }>();

  const { data: account, isLoading: accountLoading, error: accountError } = useAccount(accountId);
  const { data: txnPage, isLoading: txnLoading } = useTransactions(accountId, {
    page: 1,
    size: 20,
    type: "ALL",
  });

  if (accountError) {
    const is404 = accountError instanceof HttpError && accountError.status === 404;
    return (
      <div className="text-center py-24 space-y-4">
        <p className="text-lg font-medium">
          {is404 ? "계좌를 찾을 수 없습니다." : "오류가 발생했습니다."}
        </p>
        <Button asChild variant="outline">
          <Link href="/dashboard">대시보드로 돌아가기</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* 상단 네비게이션 */}
      <Link
        href="/dashboard"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ChevronLeft className="h-4 w-4" />
        대시보드로 돌아가기
      </Link>

      {/* 계좌 정보 카드 */}
      <AccountDetailCard
        account={account}
        isLoading={accountLoading}
        accountId={accountId}
      />

      {/* 거래 내역 */}
      <section>
        <h2 className="text-lg font-semibold mb-3">거래 내역</h2>
        <div className="rounded-xl border bg-card overflow-hidden">
          <TransactionList
            transactions={txnPage?.content ?? []}
            isLoading={txnLoading}
            grouped
          />
        </div>
      </section>
    </div>
  );
}
