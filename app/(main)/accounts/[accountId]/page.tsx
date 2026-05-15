import { AccountDetail } from "@/components/features/account/AccountDetail";

interface Props {
  params: { accountId: string };
  searchParams: { page?: string; type?: string };
}

export default function AccountDetailPage({ params, searchParams }: Props) {
  const page = Number(searchParams.page ?? "1");
  const type = (searchParams.type ?? "ALL") as "ALL" | "DEPOSIT" | "WITHDRAWAL";

  return (
    <div className="max-w-2xl mx-auto">
      <AccountDetail accountId={params.accountId} page={page} type={type} />
    </div>
  );
}
