"use client";

import { useMemo } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { PlusCircle, ChevronDown } from "lucide-react";
import { useAccounts } from "@/lib/api/hooks";
import { AccountListCard } from "@/components/features/account/AccountListCard";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { toast } from "@/hooks/use-toast";
import type { Account } from "@/lib/api/types";

type AccountTypeFilter = "ALL" | "CHECKING" | "SAVINGS";
type SortKey = "balance-desc" | "balance-asc" | "opened-desc";

const SORT_LABELS: Record<SortKey, string> = {
  "balance-desc": "잔액 높은순",
  "balance-asc": "잔액 낮은순",
  "opened-desc": "개설일 최신순",
};

function sortAccounts(accounts: Account[], sort: SortKey): Account[] {
  return [...accounts].sort((a, b) => {
    if (sort === "balance-desc" || sort === "balance-asc") {
      const ba = BigInt(a.accountBalance);
      const bb = BigInt(b.accountBalance);
      const diff = sort === "balance-desc" ? bb - ba : ba - bb;
      return diff > 0n ? 1 : diff < 0n ? -1 : 0;
    }
    return new Date(b.openedAt).getTime() - new Date(a.openedAt).getTime();
  });
}

function SummaryBar({ accounts }: { accounts: Account[] }) {
  const total = accounts.reduce((s, a) => s + BigInt(a.accountBalance), 0n);
  const checking = accounts
    .filter((a) => a.accountType === "CHECKING")
    .reduce((s, a) => s + BigInt(a.accountBalance), 0n);
  const savings = accounts
    .filter((a) => a.accountType === "SAVINGS")
    .reduce((s, a) => s + BigInt(a.accountBalance), 0n);

  return (
    <div className="grid grid-cols-3 gap-4">
      {[
        { label: "총 자산", value: total },
        { label: "보통예금", value: checking },
        { label: "저축예금", value: savings },
      ].map(({ label, value }) => (
        <Card key={label}>
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground mb-1">{label}</p>
            <p className="text-lg font-bold tabular-nums">
              {value.toLocaleString("ko-KR")}원
            </p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export default function AccountsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const type = (searchParams.get("type") ?? "ALL") as AccountTypeFilter;
  const sort = (searchParams.get("sort") ?? "balance-desc") as SortKey;

  const { data: accounts = [], isLoading, error, refetch } = useAccounts();

  const updateParams = (updates: Partial<{ type: string; sort: string }>) => {
    const params = new URLSearchParams(searchParams.toString());
    Object.entries(updates).forEach(([k, v]) => params.set(k, v));
    router.replace(`/accounts?${params}`);
  };

  const filtered = useMemo(() => {
    const typed =
      type === "ALL" ? accounts : accounts.filter((a) => a.accountType === type);
    return sortAccounts(typed, sort);
  }, [accounts, type, sort]);

  return (
    <div className="space-y-6">
      {/* 페이지 헤더 */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">내 계좌</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {isLoading ? "불러오는 중..." : `보유 중인 계좌 ${accounts.length}개`}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="gap-1.5"
          onClick={() =>
            toast({ title: "준비 중", description: "계좌 추가 기능은 준비 중입니다." })
          }
        >
          <PlusCircle className="h-4 w-4" />
          계좌 추가
        </Button>
      </div>

      {/* 요약 바 */}
      {isLoading ? (
        <div className="grid grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <CardContent className="p-4 space-y-2">
                <Skeleton className="h-3 w-16" />
                <Skeleton className="h-6 w-28" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <SummaryBar accounts={accounts} />
      )}

      {/* 필터/정렬 */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <Tabs
          value={type}
          onValueChange={(v) => updateParams({ type: v, sort })}
        >
          <TabsList>
            <TabsTrigger value="ALL">전체</TabsTrigger>
            <TabsTrigger value="CHECKING">보통예금</TabsTrigger>
            <TabsTrigger value="SAVINGS">저축예금</TabsTrigger>
          </TabsList>
        </Tabs>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" className="gap-1.5">
              {SORT_LABELS[sort]}
              <ChevronDown className="h-3.5 w-3.5" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {(Object.entries(SORT_LABELS) as [SortKey, string][]).map(([key, label]) => (
              <DropdownMenuItem
                key={key}
                onClick={() => updateParams({ type, sort: key })}
              >
                {label}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* 계좌 카드 리스트 */}
      {isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <CardContent className="p-5">
                <div className="flex items-center gap-4">
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-5 w-20" />
                    <Skeleton className="h-4 w-32" />
                    <Skeleton className="h-3 w-24" />
                  </div>
                  <Skeleton className="h-7 w-36" />
                  <div className="flex gap-1">
                    <Skeleton className="h-8 w-20" />
                    <Skeleton className="h-8 w-20" />
                    <Skeleton className="h-8 w-8" />
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : error ? (
        <div className="text-center py-12 space-y-3">
          <p className="text-muted-foreground">계좌 정보를 불러오지 못했습니다.</p>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            재시도
          </Button>
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 space-y-3">
          <p className="text-muted-foreground">
            {accounts.length === 0
              ? "보유 중인 계좌가 없습니다."
              : "해당 조건의 계좌가 없습니다."}
          </p>
          {accounts.length === 0 && (
            <Button
              size="sm"
              onClick={() =>
                toast({ title: "준비 중", description: "계좌 개설 기능은 준비 중입니다." })
              }
            >
              계좌 개설하기
            </Button>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((account) => (
            <AccountListCard key={account.accountId} account={account} />
          ))}
        </div>
      )}
    </div>
  );
}
