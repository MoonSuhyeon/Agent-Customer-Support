import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import type { Transaction } from "@/lib/api/types";

interface Props {
  transactions: Transaction[];
  isLoading?: boolean;
}

function formatDate(isoStr: string) {
  const d = new Date(isoStr);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

export function TransactionList({ transactions, isLoading }: Props) {
  if (isLoading) {
    return (
      <div className="px-6 space-y-1">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex justify-between items-center py-3">
            <div className="space-y-1.5">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-3 w-16" />
            </div>
            <Skeleton className="h-4 w-20" />
          </div>
        ))}
      </div>
    );
  }

  if (transactions.length === 0) {
    return (
      <p className="text-center py-10 text-sm text-muted-foreground">
        최근 거래 내역이 없습니다.
      </p>
    );
  }

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
