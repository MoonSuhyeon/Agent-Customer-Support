"use client";

import { useRouter } from "next/navigation";
import { Card, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { LoanProduct } from "@/lib/api/types";

interface Props {
  product: LoanProduct;
}

export function LoanProductCard({ product }: Props) {
  const router = useRouter();

  return (
    <Card className="flex flex-col">
      <CardContent className="p-5 flex-1">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="font-semibold">{product.productName}</h3>
            <p className="text-sm text-muted-foreground mt-1">{product.description}</p>
          </div>
          <Badge variant="secondary" className="shrink-0 text-xs">
            대출
          </Badge>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
          <div>
            <p className="text-muted-foreground text-xs mb-0.5">최대 한도</p>
            <p className="font-semibold">
              {Number(product.maxAmount).toLocaleString("ko-KR")}원
            </p>
          </div>
          <div>
            <p className="text-muted-foreground text-xs mb-0.5">최저 금리</p>
            <p className="font-semibold text-blue-600">{product.minRate}%~</p>
          </div>
        </div>
      </CardContent>
      <CardFooter className="px-5 pb-5 pt-0">
        <Button
          className="w-full"
          onClick={() => router.push(`/loans/apply?productId=${product.productId}`)}
        >
          신청하기
        </Button>
      </CardFooter>
    </Card>
  );
}
