import { Settings } from "lucide-react";

export default function SettingsPage() {
  return (
    <div className="flex flex-col items-center justify-center py-24 gap-4 text-center">
      <Settings className="h-12 w-12 text-muted-foreground" />
      <h1 className="text-xl font-semibold">설정</h1>
      <p className="text-muted-foreground">준비 중인 기능입니다.</p>
    </div>
  );
}
