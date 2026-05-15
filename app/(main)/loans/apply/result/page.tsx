"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { CheckCircle2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

function ResultRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-3">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-semibold">{value}</span>
    </div>
  );
}

export default function LoanApplyResultPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const id = searchParams.get("id") ?? "-";
  const product = searchParams.get("product") ?? "-";
  const amount = searchParams.get("amount") ?? "0";
  const rate = searchParams.get("rate") ?? "0";
  const monthly = searchParams.get("monthly") ?? "0";
  const term = searchParams.get("term") ?? "0";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">심사 결과</h1>
        <p className="text-sm text-muted-foreground mt-0.5">대출 신청이 완료되었습니다.</p>
      </div>

      <Card>
        <CardContent className="p-6 space-y-6">
          <div className="flex flex-col items-center gap-3 py-4">
            <CheckCircle2 className="h-14 w-14 text-green-500" />
            <div className="text-center">
              <p className="text-lg font-bold text-green-600">승인</p>
              <p className="text-sm text-muted-foreground mt-1">신청 번호: {id}</p>
            </div>
          </div>

          <Separator />

          <div className="divide-y">
            <ResultRow label="대출 상품" value={product} />
            <ResultRow
              label="승인 금액"
              value={`${Number(amount).toLocaleString("ko-KR")}원`}
            />
            <ResultRow label="적용 금리" value={`${rate}%`} />
            <ResultRow label="대출 기간" value={`${term}개월`} />
            <ResultRow
              label="월 상환액"
              value={`${Number(monthly).toLocaleString("ko-KR")}원`}
            />
          </div>

          <Button className="w-full" onClick={() => router.push("/loans")}>
            확인
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
