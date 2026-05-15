"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeftRight, ChevronRight } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { Account } from "@/lib/api/types";

interface Props {
  account: Account;
}

const TYPE_LABEL: Record<Account["accountType"], string> = {
  CHECKING: "보통예금",
  SAVINGS: "저축예금",
};

export function AccountCard({ account }: Props) {
  const router = useRouter();

  return (
    <Card
      className="cursor-pointer hover:shadow-md transition-shadow"
      onClick={() => router.push(`/accounts/${account.accountId}`)}
    >
      <CardContent className="p-5 space-y-3">
        <div className="flex items-center justify-between">
          <Badge variant="secondary">{TYPE_LABEL[account.accountType]}</Badge>
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        </div>

        <div>
          <p className="text-xs text-muted-foreground">{account.accountNo}</p>
          <p className="text-xl font-bold mt-0.5">
            {Number(account.accountBalance).toLocaleString("ko-KR")}원
          </p>
        </div>

        <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
          <Button variant="outline" size="sm" asChild>
            <Link
              href={`/transfer?fromAccountId=${account.accountId}`}
              className="gap-1.5"
            >
              <ArrowLeftRight className="h-3.5 w-3.5" />
              이체
            </Link>
          </Button>
          <Button variant="ghost" size="sm" asChild>
            <Link href={`/accounts/${account.accountId}`}>상세</Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
