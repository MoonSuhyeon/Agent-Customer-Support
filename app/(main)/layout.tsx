import { AppHeader } from "@/components/features/layout/AppHeader";
import { AppSidebar } from "@/components/features/layout/AppSidebar";

export default function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col">
      <AppHeader />
      <div className="flex flex-1">
        {/* 사이드바 (데스크탑 lg 이상) */}
        <aside className="hidden lg:flex w-60 shrink-0 border-r bg-white flex-col">
          <AppSidebar />
        </aside>

        {/* 메인 콘텐츠 */}
        <main className="flex-1 bg-gray-50 py-6 px-8">
          <div className="max-w-[1280px] mx-auto">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
