"use client";

import { useRouter } from "next/navigation";
import { CalendarDays } from "lucide-react";
import { useLoanProducts, useMyLoans } from "@/lib/api/hooks";
import { LoanProductCard } from "@/components/features/loan/LoanProductCard";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

function MyLoanSection() {
  const router = useRouter();
  const { data: loans = [], isLoading } = useMyLoans();

  if (isLoading) {
    return (
      <Card>
        <CardContent className="p-5 space-y-3">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-4 w-56" />
        </CardContent>
      </Card>
    );
  }

  if (loans.length === 0) {
    return (
      <Card>
        <CardContent className="p-5 text-sm text-muted-foreground">
          보유 중인 대출이 없습니다.
        </CardContent>
      </Card>
    );
  }

  const loan = loans[0];

  return (
    <Card>
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-3 flex-1">
            <div className="flex items-center gap-2">
              <Badge variant="secondary">{loan.productName}</Badge>
              <span className="text-xs text-muted-foreground">현재 대출 {loans.length}건</span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
              <div>
                <p className="text-muted-foreground text-xs mb-0.5">대출 원금</p>
                <p className="font-semibold">
                  {Number(loan.principalAmount).toLocaleString("ko-KR")}원
                </p>
              </div>
              <div>
                <p className="text-muted-foreground text-xs mb-0.5">잔여 원금</p>
                <p className="font-semibold">
                  {Number(loan.remainingAmount).toLocaleString("ko-KR")}원
                </p>
              </div>
              <div>
                <p className="text-muted-foreground text-xs mb-0.5">적용 금리</p>
                <p className="font-semibold text-blue-600">{loan.interestRate}%</p>
              </div>
              <div>
                <p className="text-muted-foreground text-xs mb-0.5">월 상환액</p>
                <p className="font-semibold">
                  {Number(loan.monthlyPayment).toLocaleString("ko-KR")}원
                </p>
              </div>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <CalendarDays className="h-3.5 w-3.5" />
              다음 상환일: {loan.nextPaymentDate}
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => router.push(`/loans/${loan.loanId}`)}
          >
            상세보기
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function ProductSection() {
  const { data: products = [], isLoading } = useLoanProducts();

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <Card key={i}>
            <CardContent className="p-5 space-y-3">
              <Skeleton className="h-5 w-28" />
              <Skeleton className="h-4 w-44" />
              <div className="grid grid-cols-2 gap-3 pt-1">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      {products.map((product) => (
        <LoanProductCard key={product.productId} product={product} />
      ))}
    </div>
  );
}

export default function LoansPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">대출</h1>
        <p className="text-sm text-muted-foreground mt-0.5">맞춤 대출 상품을 확인하세요.</p>
      </div>

      <section className="space-y-3">
        <h2 className="text-base font-semibold">내 대출 현황</h2>
        <MyLoanSection />
      </section>

      <section className="space-y-3">
        <h2 className="text-base font-semibold">대출 상품</h2>
        <ProductSection />
      </section>
    </div>
  );
}
