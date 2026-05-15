"use client";

import { useMemo } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useAccounts, useTransactions } from "@/lib/api/hooks";
import { TransactionList } from "@/components/features/transaction/TransactionList";
import { TransactionFilter } from "@/components/features/transaction/TransactionFilter";
import { TransactionPagination } from "@/components/features/transaction/TransactionPagination";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import type { TransactionType } from "@/lib/api/types";

const BASE_PATH = "/transactions";

export default function TransactionsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const { data: accounts = [], isLoading: accountsLoading, error: accountsError, refetch } = useAccounts();

  const firstAccountId = accounts[0]?.accountId ?? "";
  const accountId = searchParams.get("accountId") ?? firstAccountId;
  const type = (searchParams.get("type") ?? "ALL") as TransactionType;
  const page = Math.max(1, Number(searchParams.get("page") ?? "1"));

  const { data: txnPage, isLoading: txnLoading } = useTransactions(
    accountId,
    { page, size: 20, type },
  );

  const basePath = useMemo(() => {
    if (!accountId) return BASE_PATH;
    return `${BASE_PATH}?accountId=${accountId}`;
  }, [accountId]);

  const updateParams = (updates: Record<string, string>) => {
    const params = new URLSearchParams(searchParams.toString());
    Object.entries(updates).forEach(([k, v]) => params.set(k, v));
    if (!params.has("accountId") && firstAccountId) {
      params.set("accountId", firstAccountId);
    }
    router.replace(`${BASE_PATH}?${params}`);
  };

  if (accountsError) {
    return (
      <div className="text-center py-24 space-y-3">
        <p className="text-muted-foreground">계좌 정보를 불러오지 못했습니다.</p>
        <Button variant="outline" size="sm" onClick={() => refetch()}>재시도</Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">거래 내역</h1>
        <p className="text-sm text-muted-foreground mt-0.5">계좌별 입출금 내역을 확인합니다.</p>
      </div>

      {/* 계좌 선택 + 타입 필터 */}
      <div className="flex items-center gap-3 flex-wrap">
        {accountsLoading ? (
          <Skeleton className="h-9 w-48" />
        ) : (
          <Select
            value={accountId}
            onValueChange={(v) => updateParams({ accountId: v, type: "ALL", page: "1" })}
          >
            <SelectTrigger className="w-52">
              <SelectValue placeholder="계좌 선택" />
            </SelectTrigger>
            <SelectContent>
              {accounts.map((a) => (
                <SelectItem key={a.accountId} value={a.accountId}>
                  {a.accountNo}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        {accountId && (
          <TransactionFilter
            accountId={accountId}
            current={type}
            basePath={`${BASE_PATH}?accountId=${accountId}`}
          />
        )}
      </div>

      {/* 거래 내역 카드 */}
      <Card>
        <TransactionList
          transactions={txnPage?.content ?? []}
          isLoading={txnLoading && !txnPage}
          grouped
        />
        {txnPage && (
          <TransactionPagination
            accountId={accountId}
            currentPage={txnPage.currentPage}
            totalPages={txnPage.totalPages}
            type={type}
            basePath={`${BASE_PATH}?accountId=${accountId}`}
          />
        )}
        {!txnLoading && txnPage?.content.length === 0 && (
          <CardContent className="py-16 text-center text-sm text-muted-foreground">
            거래 내역이 없습니다.
          </CardContent>
        )}
      </Card>
    </div>
  );
}
