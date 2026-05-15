import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { Account } from "@/lib/api/types";

interface Props {
  accounts: Account[];
  isLoading: boolean;
}

const MOCK_MONTHLY_SPENDING = "850000";

export function AccountSummary({ accounts, isLoading }: Props) {
  const totalAssets = accounts.reduce((sum, a) => sum + BigInt(a.accountBalance), 0n);

  const items = [
    {
      label: "총 자산",
      value: `${totalAssets.toLocaleString("ko-KR")}원`,
    },
    {
      label: "계좌 수",
      value: `${accounts.length}개`,
    },
    {
      label: "이번 달 지출",
      value: `${Number(MOCK_MONTHLY_SPENDING).toLocaleString("ko-KR")}원`,
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {items.map(({ label, value }) => (
        <Card key={label}>
          <CardContent className="p-5">
            <p className="text-sm text-muted-foreground mb-1">{label}</p>
            {isLoading ? (
              <Skeleton className="h-8 w-36 mt-1" />
            ) : (
              <p className="text-2xl font-bold">{value}</p>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
