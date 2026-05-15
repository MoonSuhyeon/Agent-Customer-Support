"use client";

import { useTheme } from "next-themes";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export function DisplayTab() {
  const { resolvedTheme, setTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label htmlFor="dark-mode" className="text-sm font-medium cursor-pointer">
            다크 모드
          </Label>
          <p className="text-sm text-muted-foreground">어두운 테마를 사용합니다.</p>
        </div>
        <Switch
          id="dark-mode"
          checked={isDark}
          onCheckedChange={(v) => setTheme(v ? "dark" : "light")}
        />
      </div>

      <Separator />

      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label className="text-sm font-medium">언어</Label>
          <p className="text-sm text-muted-foreground">앱 표시 언어를 선택합니다.</p>
        </div>
        <Select defaultValue="ko">
          <SelectTrigger className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="ko">한국어</SelectItem>
            <SelectItem value="en">English</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
