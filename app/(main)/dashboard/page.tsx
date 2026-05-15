"use client";

import Link from "next/link";
import { PlusCircle, ArrowRight, Send } from "lucide-react";
import { useAccounts } from "@/lib/api/hooks";
import { useTransactions } from "@/lib/api/hooks";
import { AccountCard } from "@/components/features/account/AccountCard";
import { AccountSummary } from "@/components/features/account/AccountSummary";
import { TransactionList } from "@/components/features/transaction/TransactionList";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const QUICK_TRANSFERS = [
  { name: "김철수", accountNo: "220-1111-2222", bank: "신한은행" },
  { name: "이영희", accountNo: "220-3333-4444", bank: "국민은행" },
  { name: "박민준", accountNo: "330-5555-6666", bank: "우리은행" },
];

function todayStr() {
  const d = new Date();
  const days = ["일", "월", "화", "수", "목", "금", "토"];
  return `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일 ${days[d.getDay()]}요일`;
}

export default function DashboardPage() {
  const { data: accounts = [], isLoading: accountsLoading, error: accountsError, refetch } = useAccounts();
  const firstAccountId = accounts[0]?.accountId ?? "";
  const { data: txnPage, isLoading: txnLoading } = useTransactions(firstAccountId, { size: 5 });
  const recentTxns = txnPage?.content ?? [];

  return (
    <div className="space-y-8">
      {/* 인사말 */}
      <div>
        <h1 className="text-2xl font-bold">안녕하세요, 홍길동님</h1>
        <p className="text-muted-foreground mt-1">{todayStr()}</p>
      </div>

      {/* 요약 카드 3개 */}
      <AccountSummary accounts={accounts} isLoading={accountsLoading} />

      {/* 내 계좌 섹션 */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">내 계좌</h2>
          <Button variant="outline" size="sm" className="gap-1.5">
            <PlusCircle className="h-4 w-4" />
            계좌 추가
          </Button>
        </div>

        {accountsLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <Card key={i}>
                <CardContent className="p-5 space-y-3">
                  <Skeleton className="h-4 w-20" />
                  <Skeleton className="h-4 w-32" />
                  <Skeleton className="h-7 w-36" />
                  <div className="flex gap-2 pt-1">
                    <Skeleton className="h-8 w-16" />
                    <Skeleton className="h-8 w-16" />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : accountsError ? (
          <div className="text-center py-12 space-y-3">
            <p className="text-muted-foreground">계좌 정보를 불러오지 못했습니다.</p>
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              재시도
            </Button>
          </div>
        ) : accounts.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            계좌를 개설해보세요.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {accounts.map((account) => (
              <AccountCard key={account.accountId} account={account} />
            ))}
          </div>
        )}
      </section>

      {/* 하단 2열 영역 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 최근 거래 */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <CardTitle className="text-base">최근 거래</CardTitle>
            {firstAccountId && (
              <Link
                href={`/accounts/${firstAccountId}`}
                className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors"
              >
                전체 보기
                <ArrowRight className="h-3 w-3" />
              </Link>
            )}
          </CardHeader>
          <CardContent className="p-0 pb-2">
            <TransactionList transactions={recentTxns} isLoading={txnLoading} />
          </CardContent>
        </Card>

        {/* 빠른 이체 */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">빠른 이체</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            {QUICK_TRANSFERS.map((item) => (
              <div key={item.accountNo} className="flex items-center justify-between py-2.5">
                <div>
                  <p className="text-sm font-medium">{item.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {item.bank} · {item.accountNo}
                  </p>
                </div>
                <Button variant="outline" size="sm" asChild>
                  <Link href="/transfer" className="gap-1.5">
                    <Send className="h-3 w-3" />
                    이체
                  </Link>
                </Button>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
