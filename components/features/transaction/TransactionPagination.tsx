"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { TransactionType } from "@/lib/api/types";

interface Props {
  accountId: string;
  currentPage: number;
  totalPages: number;
  type: TransactionType;
}

export function TransactionPagination({ accountId, currentPage, totalPages, type }: Props) {
  const router = useRouter();

  if (totalPages <= 1) return null;

  const go = (page: number) => {
    const params = new URLSearchParams({ type, page: String(page) });
    router.replace(`/accounts/${accountId}?${params}`);
  };

  return (
    <div className="flex items-center justify-between px-4 py-3 border-t">
      <Button
        variant="ghost"
        size="sm"
        disabled={currentPage <= 1}
        onClick={() => go(currentPage - 1)}
        className="gap-1"
      >
        <ChevronLeft className="h-4 w-4" />
        이전
      </Button>
      <span className="text-sm text-muted-foreground tabular-nums">
        {currentPage} / {totalPages}
      </span>
      <Button
        variant="ghost"
        size="sm"
        disabled={currentPage >= totalPages}
        onClick={() => go(currentPage + 1)}
        className="gap-1"
      >
        다음
        <ChevronRight className="h-4 w-4" />
      </Button>
    </div>
  );
}
