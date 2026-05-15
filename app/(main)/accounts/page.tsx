"use client";

import { PlusCircle } from "lucide-react";
import { useAccounts } from "@/lib/api/hooks";
import { AccountCard } from "@/components/features/account/AccountCard";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export default function AccountsPage() {
  const { data: accounts = [], isLoading, error, refetch } = useAccounts();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">내 계좌</h1>
        <Button variant="outline" size="sm" className="gap-1.5">
          <PlusCircle className="h-4 w-4" />
          계좌 추가
        </Button>
      </div>

      {isLoading ? (
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
      ) : error ? (
        <div className="text-center py-12 space-y-3">
          <p className="text-muted-foreground">계좌 정보를 불러오지 못했습니다.</p>
          <Button variant="outline" size="sm" onClick={() => refetch()}>재시도</Button>
        </div>
      ) : accounts.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          개설된 계좌가 없습니다.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {accounts.map((account) => (
            <AccountCard key={account.accountId} account={account} />
          ))}
        </div>
      )}
    </div>
  );
}
