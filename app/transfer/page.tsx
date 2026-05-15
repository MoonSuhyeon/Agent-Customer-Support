import { TransferForm } from "@/components/features/transfer/TransferForm";

interface Props {
  searchParams: { fromAccountId?: string };
}

export default function TransferPage({ searchParams }: Props) {
  return (
    <main className="min-h-screen bg-gray-50 flex items-start justify-center py-10 px-4">
      <TransferForm defaultFromAccountId={searchParams.fromAccountId} />
    </main>
  );
}
