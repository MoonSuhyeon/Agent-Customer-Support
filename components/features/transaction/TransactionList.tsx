import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { TransactionItem } from "./TransactionItem";
import type { Transaction } from "@/lib/api/types";

interface Props {
  transactions: Transaction[];
  isLoading?: boolean;
  grouped?: boolean;
}

function formatDate(isoStr: string) {
  const d = new Date(isoStr);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

function formatDateFull(dateStr: string) {
  const d = new Date(dateStr);
  return d.toLocaleDateString("ko-KR", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "short",
  });
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

export function TransactionList({ transactions, isLoading, grouped = false }: Props) {
  if (isLoading) {
    return (
      <div className={grouped ? "p-0" : "px-6 space-y-1"}>
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className={`flex justify-between items-center ${grouped ? "px-4 py-3" : "py-3"}`}>
            <div className="space-y-1.5">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-3 w-16" />
            </div>
            <div className="space-y-1.5 text-right">
              <Skeleton className="h-4 w-20" />
              {grouped && <Skeleton className="h-3 w-16" />}
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (transactions.length === 0) {
    return (
      <p className="text-center py-10 text-sm text-muted-foreground">
        거래 내역이 없습니다.
      </p>
    );
  }

  /* ── 날짜 그룹핑 모드 (계좌 상세) ── */
  if (grouped) {
    return (
      <div>
        {groupByDate(transactions).map(([date, txns]) => (
          <div key={date}>
            <div className="px-4 py-2 bg-muted/50 text-xs text-muted-foreground font-medium">
              {formatDateFull(date)}
            </div>
            {txns.map((txn, i) => (
              <TransactionItem
                key={txn.transactionId}
                transaction={txn}
                showSeparator={i < txns.length - 1}
              />
            ))}
          </div>
        ))}
      </div>
    );
  }

  /* ── 단순 목록 모드 (대시보드) ── */
  return (
    <div>
      {transactions.map((txn, i) => {
        const isDeposit = txn.transactionType === "DEPOSIT";
        return (
          <div key={txn.transactionId}>
            <div className="flex items-center justify-between px-6 py-3">
              <div>
                <p className="text-sm font-medium">{txn.counterpartyName}</p>
                <p className="text-xs text-muted-foreground">
                  {formatDate(txn.transactionAt)} · {txn.transactionMemo}
                </p>
              </div>
              <span
                className={`text-sm font-semibold tabular-nums ${
                  isDeposit ? "text-blue-600" : "text-red-500"
                }`}
              >
                {isDeposit ? "+" : "-"}
                {Number(txn.transactionAmount).toLocaleString("ko-KR")}원
              </span>
            </div>
            {i < transactions.length - 1 && <Separator />}
          </div>
        );
      })}
    </div>
  );
}
