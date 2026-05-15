"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { HttpError } from "@/lib/api/client";
import { useAccount, useTransactions } from "@/lib/api/hooks";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import type { Transaction, TransactionType } from "@/lib/api/types";

interface Props {
  accountId: string;
  page: number;
  type: TransactionType;
}

const TYPE_LABELS: Record<TransactionType, string> = {
  ALL: "전체",
  DEPOSIT: "입금",
  WITHDRAWAL: "출금",
};

function typeUrl(accountId: string, type: TransactionType, page = 1) {
  return `/accounts/${accountId}?type=${type}&page=${page}`;
}

function groupByDate(txns: Transaction[]): [string, Transaction[]][] {
  const map = new Map<string, Transaction[]>();
  for (const t of txns) {
    const date = t.transactionAt.slice(0, 10);
    if (!map.has(date)) map.set(date, []);
    map.get(date)!.push(t);
  }
  return Array.from(map.entries());
}

function formatDate(dateStr: string) {
  const d = new Date(dateStr);
  return d.toLocaleDateString("ko-KR", { year: "numeric", month: "long", day: "numeric", weekday: "short" });
}

function formatTime(isoStr: string) {
  const d = new Date(isoStr);
  return d.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" });
}

export function AccountDetail({ accountId, page, type }: Props) {
  const router = useRouter();
  const {
    data: account,
    isLoading: accountLoading,
    error: accountError,
  } = useAccount(accountId);

  const {
    data: txnPage,
    isLoading: txnLoading,
  } = useTransactions(accountId, { page, type, size: 20 });

  if (accountError) {
    const is404 = accountError instanceof HttpError && accountError.status === 404;
    return (
      <div className="text-center py-20 space-y-3">
        <p className="text-lg font-medium">{is404 ? "계좌를 찾을 수 없습니다." : "오류가 발생했습니다."}</p>
        <Button variant="outline" onClick={() => router.back()}>뒤로가기</Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* 계좌 카드 */}
      {accountLoading ? (
        <div className="rounded-xl border bg-card p-6 space-y-3">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-4 w-32" />
        </div>
      ) : account ? (
        <div className="rounded-xl border bg-card p-6 space-y-1">
          <p className="text-sm text-muted-foreground">{account.accountNo}</p>
          <p className="text-2xl font-bold">
            {Number(account.accountBalance).toLocaleString("ko-KR")}원
          </p>
          <div className="flex items-center gap-2 pt-1">
            <span className="text-sm text-muted-foreground">{account.accountHolder}</span>
            <Badge variant="secondary">
              {account.accountType === "CHECKING" ? "입출금" : "저축"}
            </Badge>
            {account.accountStatus !== "ACTIVE" && (
              <Badge variant="destructive">{account.accountStatus}</Badge>
            )}
          </div>
          <div className="pt-3">
            <Link href={`/transfer?fromAccountId=${accountId}`}>
              <Button size="sm">이 계좌에서 이체</Button>
            </Link>
          </div>
        </div>
      ) : null}

      {/* 필터 탭 */}
      <div className="flex gap-1 rounded-lg border bg-card p-1">
        {(["ALL", "DEPOSIT", "WITHDRAWAL"] as TransactionType[]).map((t) => (
          <Link
            key={t}
            href={typeUrl(accountId, t)}
            className={`flex-1 text-center text-sm py-1.5 rounded-md transition-colors ${
              type === t
                ? "bg-primary text-primary-foreground font-medium"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {TYPE_LABELS[t]}
          </Link>
        ))}
      </div>

      {/* 거래 내역 */}
      <div className="rounded-xl border bg-card overflow-hidden">
        {txnLoading ? (
          <div className="p-4 space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex justify-between items-center">
                <div className="space-y-1.5">
                  <Skeleton className="h-4 w-28" />
                  <Skeleton className="h-3 w-20" />
                </div>
                <Skeleton className="h-5 w-24" />
              </div>
            ))}
          </div>
        ) : !txnPage || txnPage.content.length === 0 ? (
          <div className="py-16 text-center text-sm text-muted-foreground">
            거래 내역이 없습니다.
          </div>
        ) : (
          groupByDate(txnPage.content).map(([date, txns]) => (
            <div key={date}>
              <div className="px-4 py-2 bg-muted/50 text-xs text-muted-foreground font-medium">
                {formatDate(date)}
              </div>
              {txns.map((txn, i) => {
                const isDeposit = txn.transactionType === "DEPOSIT";
                return (
                  <div key={txn.transactionId}>
                    <div className="flex items-center justify-between px-4 py-3">
                      <div className="space-y-0.5 min-w-0">
                        <p className="text-sm font-medium truncate">{txn.counterpartyName}</p>
                        <p className="text-xs text-muted-foreground">
                          {formatTime(txn.transactionAt)}
                          {txn.transactionMemo && ` · ${txn.transactionMemo}`}
                        </p>
                      </div>
                      <div className="text-right shrink-0 ml-4">
                        <p className={`text-sm font-semibold ${isDeposit ? "text-blue-600" : "text-foreground"}`}>
                          {isDeposit ? "+" : "-"}
                          {Number(txn.transactionAmount).toLocaleString("ko-KR")}원
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {Number(txn.balanceAfter).toLocaleString("ko-KR")}원
                        </p>
                      </div>
                    </div>
                    {i < txns.length - 1 && <Separator />}
                  </div>
                );
              })}
            </div>
          ))
        )}
      </div>

      {/* 페이지네이션 */}
      {txnPage && txnPage.totalPages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => router.push(typeUrl(accountId, type, page - 1))}
          >
            이전
          </Button>
          <span className="text-muted-foreground">
            {page} / {txnPage.totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= txnPage.totalPages}
            onClick={() => router.push(typeUrl(accountId, type, page + 1))}
          >
            다음
          </Button>
        </div>
      )}
    </div>
  );
}
