"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { LoanApplyForm } from "@/components/features/loan/LoanApplyForm";

export default function LoanApplyPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const productId = searchParams.get("productId") ?? undefined;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => router.back()}>
          <ChevronLeft className="h-5 w-5" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold">대출 신청</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            원하는 상품을 선택하고 정보를 입력해주세요.
          </p>
        </div>
      </div>

      <Card>
        <CardContent className="p-6">
          <LoanApplyForm initialProductId={productId} />
        </CardContent>
      </Card>
    </div>
  );
}
