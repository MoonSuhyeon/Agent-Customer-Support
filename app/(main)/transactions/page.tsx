"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAccounts } from "@/lib/api/hooks";
import { Skeleton } from "@/components/ui/skeleton";

export default function TransactionsPage() {
  const router = useRouter();
  const { data: accounts = [], isLoading } = useAccounts();

  useEffect(() => {
    if (!isLoading && accounts.length > 0) {
      router.replace(`/accounts/${accounts[0].accountId}?type=ALL`);
    }
  }, [accounts, isLoading, router]);

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      <Skeleton className="h-8 w-32" />
      <div className="rounded-xl border bg-card p-6 space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    </div>
  );
}
