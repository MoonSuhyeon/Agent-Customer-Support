"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, CreditCard, ArrowLeftRight, List, Landmark, Settings } from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/dashboard", label: "홈", icon: Home },
  { href: "/accounts", label: "내 계좌", icon: CreditCard },
  { href: "/transfer", label: "이체", icon: ArrowLeftRight },
  { href: "/transactions", label: "거래 내역", icon: List },
  { href: "/loans", label: "대출", icon: Landmark },
  { href: "/settings", label: "설정", icon: Settings },
];

interface AppSidebarProps {
  onNavigate?: () => void;
}

export function AppSidebar({ onNavigate }: AppSidebarProps) {
  const pathname = usePathname();

  return (
    <nav className="flex flex-col gap-1 p-4">
      {navItems.map(({ href, label, icon: Icon }) => {
        const active = pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
              active
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            <Icon className="h-4 w-4 shrink-0" />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
