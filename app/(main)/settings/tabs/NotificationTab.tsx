"use client";

import { useState } from "react";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { toast } from "@/hooks/use-toast";

interface NotificationItem {
  id: string;
  label: string;
  description: string;
}

const NOTIFICATION_ITEMS: NotificationItem[] = [
  {
    id: "email-transaction",
    label: "이메일 거래 알림",
    description: "입출금 발생 시 이메일로 알림을 받습니다.",
  },
  {
    id: "email-security",
    label: "이메일 보안 알림",
    description: "로그인 및 비밀번호 변경 시 이메일로 알림을 받습니다.",
  },
  {
    id: "push-transaction",
    label: "푸시 거래 알림",
    description: "입출금 발생 시 기기 알림을 받습니다.",
  },
  {
    id: "push-marketing",
    label: "마케팅 수신 동의",
    description: "이벤트 및 혜택 정보를 받습니다.",
  },
];

export function NotificationTab() {
  const [enabled, setEnabled] = useState<Record<string, boolean>>({
    "email-transaction": true,
    "email-security": true,
    "push-transaction": false,
    "push-marketing": false,
  });

  const handleChange = (id: string, value: boolean) => {
    setEnabled((prev) => ({ ...prev, [id]: value }));
    toast({ title: "설정이 저장되었습니다." });
  };

  return (
    <div className="space-y-6">
      {NOTIFICATION_ITEMS.map((item, idx) => (
        <div key={item.id}>
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor={item.id} className="text-sm font-medium cursor-pointer">
                {item.label}
              </Label>
              <p className="text-sm text-muted-foreground">{item.description}</p>
            </div>
            <Switch
              id={item.id}
              checked={enabled[item.id]}
              onCheckedChange={(v) => handleChange(item.id, v)}
            />
          </div>
          {idx < NOTIFICATION_ITEMS.length - 1 && <Separator className="mt-6" />}
        </div>
      ))}
    </div>
  );
}
