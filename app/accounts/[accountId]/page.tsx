import { AccountDetail } from "@/components/features/account/AccountDetail";

interface Props {
  params: { accountId: string };
  searchParams: { page?: string; type?: string };
}

export default function AccountDetailPage({ params, searchParams }: Props) {
  const page = Number(searchParams.page ?? "1");
  const type = (searchParams.type ?? "ALL") as "ALL" | "DEPOSIT" | "WITHDRAWAL";

  return (
    <main className="min-h-screen bg-gray-50 flex justify-center py-10 px-4">
      <div className="w-full max-w-2xl space-y-4">
        <AccountDetail accountId={params.accountId} page={page} type={type} />
      </div>
    </main>
  );
}
