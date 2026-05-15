"use client";

import { useRouter } from "next/navigation";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { TransactionType } from "@/lib/api/types";

interface Props {
  accountId: string;
  current: TransactionType;
  basePath?: string;
}

const TABS: { value: TransactionType; label: string }[] = [
  { value: "ALL", label: "전체" },
  { value: "DEPOSIT", label: "입금" },
  { value: "WITHDRAWAL", label: "출금" },
];

export function TransactionFilter({ accountId, current, basePath }: Props) {
  const router = useRouter();

  const handleChange = (value: string) => {
    const base = basePath ?? `/accounts/${accountId}`;
    const [pathname, existingSearch] = base.split("?");
    const params = new URLSearchParams(existingSearch ?? "");
    params.set("type", value);
    params.set("page", "1");
    router.replace(`${pathname}?${params}`);
  };

  return (
    <Tabs value={current} onValueChange={handleChange}>
      <TabsList>
        {TABS.map(({ value, label }) => (
          <TabsTrigger key={value} value={value}>
            {label}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  );
}
