"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import { HttpError } from "@/lib/api/client";
import { useAccount, useTransactions } from "@/lib/api/hooks";
import { AccountDetailCard } from "@/components/features/account/AccountDetailCard";
import { TransactionList } from "@/components/features/transaction/TransactionList";
import { TransactionFilter } from "@/components/features/transaction/TransactionFilter";
import { TransactionPagination } from "@/components/features/transaction/TransactionPagination";
import { Button } from "@/components/ui/button";
import type { TransactionType } from "@/lib/api/types";

export default function AccountDetailPage() {
  const { accountId } = useParams<{ accountId: string }>();
  const searchParams = useSearchParams();

  const page = Math.max(1, Number(searchParams.get("page") ?? "1"));
  const type = (searchParams.get("type") ?? "ALL") as TransactionType;

  const { data: account, isLoading: accountLoading, error: accountError } = useAccount(accountId);
  const { data: txnPage, isLoading: txnLoading } = useTransactions(accountId, {
    page,
    size: 20,
    type,
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
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">거래 내역</h2>
          <TransactionFilter accountId={accountId} current={type} />
        </div>

        <div
          className="rounded-xl border bg-card overflow-hidden"
          style={{ opacity: txnLoading ? 0.5 : 1, transition: "opacity 0.2s" }}
        >
          <TransactionList
            transactions={txnPage?.content ?? []}
            isLoading={txnLoading && !txnPage}
            grouped
          />
          {txnPage && (
            <TransactionPagination
              accountId={accountId}
              currentPage={page}
              totalPages={txnPage.totalPages}
              type={type}
            />
          )}
        </div>
      </section>
    </div>
  );
}
