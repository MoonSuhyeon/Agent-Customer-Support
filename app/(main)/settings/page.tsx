"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ProfileTab } from "./tabs/ProfileTab";
import { SecurityTab } from "./tabs/SecurityTab";
import { NotificationTab } from "./tabs/NotificationTab";
import { DisplayTab } from "./tabs/DisplayTab";

const TABS = [
  { value: "profile", label: "프로필" },
  { value: "security", label: "보안" },
  { value: "notification", label: "알림" },
  { value: "display", label: "화면 설정" },
] as const;

type TabValue = (typeof TABS)[number]["value"];

export default function SettingsPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const tab = (searchParams.get("tab") ?? "profile") as TabValue;

  const handleTabChange = (value: string) => {
    router.replace(`/settings?tab=${value}`);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">설정</h1>
        <p className="text-sm text-muted-foreground mt-0.5">계정과 앱 환경을 관리합니다.</p>
      </div>

      <Tabs value={tab} onValueChange={handleTabChange}>
        <TabsList className="w-full justify-start h-auto p-0 bg-transparent border-b rounded-none gap-0">
          {TABS.map(({ value, label }) => (
            <TabsTrigger
              key={value}
              value={value}
              className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none px-4 py-2.5 text-sm"
            >
              {label}
            </TabsTrigger>
          ))}
        </TabsList>

        <div className="pt-6 max-w-xl">
          <TabsContent value="profile" forceMount hidden={tab !== "profile"}>
            <ProfileTab />
          </TabsContent>
          <TabsContent value="security" forceMount hidden={tab !== "security"}>
            <SecurityTab />
          </TabsContent>
          <TabsContent value="notification" forceMount hidden={tab !== "notification"}>
            <NotificationTab />
          </TabsContent>
          <TabsContent value="display" forceMount hidden={tab !== "display"}>
            <DisplayTab />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
