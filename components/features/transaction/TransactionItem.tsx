import { Separator } from "@/components/ui/separator";
import type { Transaction } from "@/lib/api/types";

interface Props {
  transaction: Transaction;
  showSeparator?: boolean;
}

function formatTime(isoStr: string) {
  const d = new Date(isoStr);
  return d.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" });
}

export function TransactionItem({ transaction: txn, showSeparator }: Props) {
  const isDeposit = txn.transactionType === "DEPOSIT";

  return (
    <>
      <div className="flex items-center justify-between px-4 py-3">
        <div className="space-y-0.5 min-w-0">
          <p className="text-sm font-medium truncate">{txn.counterpartyName}</p>
          <p className="text-xs text-muted-foreground">
            {formatTime(txn.transactionAt)}
            {txn.transactionMemo && ` · ${txn.transactionMemo}`}
          </p>
        </div>
        <div className="text-right shrink-0 ml-4">
          <p
            className={`text-sm font-semibold tabular-nums ${
              isDeposit ? "text-blue-600" : "text-red-500"
            }`}
          >
            {isDeposit ? "+" : "-"}
            {Number(txn.transactionAmount).toLocaleString("ko-KR")}원
          </p>
          <p className="text-xs text-muted-foreground tabular-nums">
            {Number(txn.balanceAfter).toLocaleString("ko-KR")}원
          </p>
        </div>
      </div>
      {showSeparator && <Separator />}
    </>
  );
}
