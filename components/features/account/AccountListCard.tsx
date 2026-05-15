"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { MoreHorizontal } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { toast } from "@/hooks/use-toast";
import type { Account } from "@/lib/api/types";

interface Props {
  account: Account;
}

const TYPE_LABEL: Record<Account["accountType"], string> = {
  CHECKING: "보통예금",
  SAVINGS: "저축예금",
};

function formatOpenedAt(isoStr: string) {
  const d = new Date(isoStr);
  return `${d.getFullYear()}년 ${d.getMonth() + 1}월`;
}

export function AccountListCard({ account }: Props) {
  const router = useRouter();

  return (
    <Card
      className="cursor-pointer hover:shadow-md transition-shadow"
      onClick={() => router.push(`/accounts/${account.accountId}`)}
    >
      <CardContent className="p-5">
        <div className="flex items-center gap-4">
          {/* 좌측: 유형·계좌번호·개설일 */}
          <div className="flex-1 min-w-0 space-y-1">
            <Badge variant="secondary">{TYPE_LABEL[account.accountType]}</Badge>
            <p className="text-sm font-medium">{account.accountNo}</p>
            <p className="text-xs text-muted-foreground">
              개설일 {formatOpenedAt(account.openedAt)}
            </p>
          </div>

          {/* 중앙: 잔액 */}
          <div className="text-right shrink-0">
            <p className="text-xs text-muted-foreground mb-0.5">잔액</p>
            <p className="text-xl font-bold tabular-nums">
              {Number(account.accountBalance).toLocaleString("ko-KR")}원
            </p>
          </div>

          {/* 우측: 액션 */}
          <div className="flex items-center gap-1 shrink-0" onClick={(e) => e.stopPropagation()}>
            <Button variant="outline" size="sm" asChild>
              <Link href={`/accounts/${account.accountId}`}>상세보기</Link>
            </Button>
            <Button size="sm" asChild>
              <Link href={`/transfer?fromAccountId=${account.accountId}`}>이체하기</Link>
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="h-8 w-8">
                  <MoreHorizontal className="h-4 w-4" />
                  <span className="sr-only">더보기</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem
                  onClick={() =>
                    toast({ title: "준비 중", description: "이름 변경 기능은 준비 중입니다." })
                  }
                >
                  이름 변경
                </DropdownMenuItem>
                <DropdownMenuItem
                  className="text-destructive"
                  onClick={() =>
                    toast({ title: "준비 중", description: "계좌 해지 기능은 준비 중입니다." })
                  }
                >
                  해지
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
