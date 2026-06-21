import type { LucideIcon } from "lucide-react";
import {
  LayoutDashboard,
  GraduationCap,
  BookText,
  ListChecks,
  TrendingUp,
} from "lucide-react";

export type MobileNavItem = {
  href: string;
  label: string;
  shortLabel?: string;
  icon: LucideIcon;
  /** Match nested routes (e.g. /vocabulary/123) */
  matchNested?: boolean;
};

/** Primary mobile tabs — daily learning shortcuts */
export const MOBILE_NAV_ITEMS: MobileNavItem[] = [
  { href: "/dashboard", label: "Home", icon: LayoutDashboard },
  { href: "/study", label: "Study", icon: GraduationCap },
  { href: "/vocabulary", label: "Words", icon: BookText, matchNested: true },
  { href: "/quiz", label: "Quiz", icon: ListChecks },
  { href: "/progress", label: "Stats", icon: TrendingUp },
];

export function isMobileNavActive(pathname: string, item: MobileNavItem): boolean {
  if (item.matchNested) {
    return pathname === item.href || pathname.startsWith(`${item.href}/`);
  }
  return pathname === item.href;
}

export function getActiveMobileNavIndex(pathname: string): number {
  const idx = MOBILE_NAV_ITEMS.findIndex((item) => isMobileNavActive(pathname, item));
  return idx >= 0 ? idx : 0;
}
