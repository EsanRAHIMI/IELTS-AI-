"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Upload,
  BookText,
  Quote,
  Layers,
  GraduationCap,
  CalendarDays,
  ListChecks,
  TrendingUp,
  Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/import", label: "Import Center", icon: Upload },
  { href: "/vocabulary", label: "Vocabulary", icon: BookText },
  { href: "/phrases", label: "Phrases", icon: Quote },
  { href: "/patterns", label: "Sentence Patterns", icon: Layers },
  { href: "/study", label: "Study Mode", icon: GraduationCap },
  { href: "/daily-plan", label: "Daily Plan", icon: CalendarDays },
  { href: "/quiz", label: "Quiz", icon: ListChecks },
  { href: "/progress", label: "Progress", icon: TrendingUp },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <div className="flex h-full flex-col">
      <div className="flex h-16 items-center gap-2 border-b px-6 text-base font-semibold">
        <GraduationCap className="h-6 w-6 text-accent" />
        <span>IELTS Mastery</span>
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto p-3">
        {nav.map((item) => {
          const active = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors",
                active ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-secondary hover:text-foreground",
              )}
            >
              <Icon className="h-[18px] w-[18px]" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
