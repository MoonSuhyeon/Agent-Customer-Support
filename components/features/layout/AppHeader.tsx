"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, Bell, ChevronDown, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { AppSidebar } from "./AppSidebar";
import { cn } from "@/lib/utils";

const headerNav = [
  { href: "/dashboard", label: "대시보드" },
  { href: "/transfer", label: "이체" },
  { href: "/transactions", label: "거래내역" },
  { href: "/loans", label: "대출" },
  { href: "/settings", label: "마이페이지" },
];

export function AppHeader() {
  const pathname = usePathname();
  const [sheetOpen, setSheetOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 h-16 border-b bg-white flex items-center px-4 lg:px-6 gap-4">
      {/* 햄버거 (모바일) */}
      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetTrigger asChild>
          <Button variant="ghost" size="icon" className="lg:hidden">
            <Menu className="h-5 w-5" />
            <span className="sr-only">메뉴 열기</span>
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="w-60 p-0">
          <SheetHeader className="px-4 pt-5 pb-2">
            <SheetTitle className="text-primary font-bold text-lg">MyBank</SheetTitle>
          </SheetHeader>
          <AppSidebar onNavigate={() => setSheetOpen(false)} />
        </SheetContent>
      </Sheet>

      {/* 로고 */}
      <Link href="/" className="font-bold text-lg text-primary shrink-0">
        MyBank
      </Link>

      {/* 글로벌 네비 (데스크탑) */}
      <nav className="hidden lg:flex items-center gap-1 ml-4">
        {headerNav.map(({ href, label }) => {
          const active = pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "px-3 py-1.5 text-sm rounded-md transition-colors",
                active
                  ? "font-semibold text-foreground"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted",
              )}
            >
              {label}
            </Link>
          );
        })}
      </nav>

      {/* 우측 액션 */}
      <div className="ml-auto flex items-center gap-1">
        <Button variant="ghost" size="icon">
          <Bell className="h-5 w-5" />
          <span className="sr-only">알림</span>
        </Button>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="flex items-center gap-2 px-2">
              <Avatar>
                <AvatarFallback>홍</AvatarFallback>
              </Avatar>
              <span className="hidden sm:inline text-sm font-medium">홍길동님</span>
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-40">
            <DropdownMenuSeparator />
            <DropdownMenuItem className="text-destructive gap-2">
              <LogOut className="h-4 w-4" />
              로그아웃
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
