import Link from "next/link";
import { ArrowLeftRight } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/hooks/use-toast";
import type { Account } from "@/lib/api/types";

interface Props {
  account: Account | undefined;
  isLoading: boolean;
  accountId: string;
}

const TYPE_LABEL: Record<Account["accountType"], string> = {
  CHECKING: "보통예금",
  SAVINGS: "저축예금",
};

export function AccountDetailCard({ account, isLoading, accountId }: Props) {
  if (isLoading) {
    return (
      <Card>
        <CardContent className="p-6 space-y-5">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-2">
              <Skeleton className="h-5 w-20" />
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-4 w-20" />
            </div>
            <div className="space-y-2 text-right">
              <Skeleton className="h-4 w-12 ml-auto" />
              <Skeleton className="h-9 w-40" />
            </div>
          </div>
          <div className="flex gap-2">
            <Skeleton className="h-9 w-24" />
            <Skeleton className="h-9 w-24" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!account) return null;

  return (
    <Card>
      <CardContent className="p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <Badge variant="secondary">{TYPE_LABEL[account.accountType]}</Badge>
            <p className="text-sm text-muted-foreground pt-1">{account.accountNo}</p>
            <p className="text-sm text-muted-foreground">{account.accountHolder}</p>
          </div>
          <div className="text-right shrink-0">
            <p className="text-xs text-muted-foreground mb-1">잔액</p>
            <p className="text-3xl font-bold tabular-nums">
              {Number(account.accountBalance).toLocaleString("ko-KR")}원
            </p>
          </div>
        </div>

        <div className="flex gap-2 mt-5">
          <Button asChild>
            <Link href={`/transfer?fromAccountId=${accountId}`} className="gap-2">
              <ArrowLeftRight className="h-4 w-4" />
              이체하기
            </Link>
          </Button>
          <Button
            variant="outline"
            onClick={() => toast({ title: "준비 중", description: "입금 기능은 준비 중입니다." })}
          >
            입금하기
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
