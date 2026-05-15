import { TransferForm } from "@/components/features/transfer/TransferForm";

interface Props {
  searchParams: { fromAccountId?: string };
}

export default function TransferPage({ searchParams }: Props) {
  return (
    <div className="flex justify-center">
      <TransferForm defaultFromAccountId={searchParams.fromAccountId} />
    </div>
  );
}
