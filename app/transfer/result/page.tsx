import Link from "next/link";
import { redirect } from "next/navigation";
import { CheckCircle2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

interface Props {
  searchParams: { transferId?: string };
}

export default function ResultPage({ searchParams }: Props) {
  const { transferId } = searchParams;
  if (!transferId) redirect("/transfer");

  return (
    <main className="min-h-screen bg-gray-50 flex items-start justify-center py-10 px-4">
      <Card className="w-full max-w-md">
        <CardHeader className="items-center text-center">
          <CheckCircle2 className="h-12 w-12 text-green-500 mb-2" />
          <CardTitle>이체 완료</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-muted-foreground">이체 번호</dt>
              <dd className="font-mono font-medium">{transferId}</dd>
            </div>
            <Separator />
            <div className="flex justify-between">
              <dt className="text-muted-foreground">처리 상태</dt>
              <dd className="font-medium text-green-600">완료</dd>
            </div>
          </dl>

          <Button asChild className="w-full">
            <Link href="/transfer">새 이체</Link>
          </Button>
        </CardContent>
      </Card>
    </main>
  );
}
