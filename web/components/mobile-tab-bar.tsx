"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutGroup, motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { MOBILE_NAV_ITEMS, isMobileNavActive } from "@/lib/mobile-nav";

const spring = { type: "spring" as const, stiffness: 520, damping: 38, mass: 0.8 };

export function MobileTabBar() {
  const pathname = usePathname();

  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-40 pointer-events-none lg:hidden"
      aria-label="Main navigation"
    >
      <div className="px-safe pb-safe-or-4 pt-2">
        <LayoutGroup id="mobile-tab-bar">
          <div
            className={cn(
              "pointer-events-auto mx-auto flex max-w-md items-stretch gap-0.5 rounded-[1.75rem] border p-1.5",
              "border-white/20 bg-background/55 shadow-[0_12px_40px_-8px_rgba(0,0,0,0.25)]",
              "backdrop-blur-2xl backdrop-saturate-150",
              "dark:border-white/10 dark:bg-background/45",
              "supports-[backdrop-filter]:bg-background/50",
            )}
          >
            {MOBILE_NAV_ITEMS.map((item) => {
              const active = isMobileNavActive(pathname, item);
              const Icon = item.icon;

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className="relative flex min-w-0 flex-1 flex-col items-center justify-center gap-0.5 rounded-[1.35rem] px-1 py-2 outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {active && (
                    <motion.span
                      layoutId="mobile-tab-active-pill"
                      className="absolute inset-0 rounded-[1.35rem] bg-primary/12 shadow-sm dark:bg-white/12"
                      transition={spring}
                    />
                  )}
                  <motion.span
                    className="relative z-10 flex flex-col items-center gap-0.5"
                    animate={{
                      scale: active ? 1.02 : 1,
                      y: active ? -1 : 0,
                    }}
                    whileTap={{ scale: 0.92 }}
                    transition={spring}
                  >
                    <Icon
                      className={cn(
                        "h-[22px] w-[22px] transition-colors duration-200",
                        active ? "text-primary dark:text-accent" : "text-muted-foreground",
                      )}
                      strokeWidth={active ? 2.25 : 1.75}
                    />
                    <span
                      className={cn(
                        "max-w-full truncate text-[10px] font-medium leading-none tracking-tight transition-colors duration-200",
                        active ? "text-foreground" : "text-muted-foreground",
                      )}
                    >
                      {item.label}
                    </span>
                  </motion.span>
                </Link>
              );
            })}
          </div>
        </LayoutGroup>
      </div>
    </nav>
  );
}
