"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutGroup, motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { MOBILE_NAV_ITEMS, isMobileNavActive } from "@/lib/mobile-nav";

/** iOS-style spring — snappy with slight settle */
const tabSpring = { type: "spring" as const, stiffness: 480, damping: 32, mass: 0.72 };
const iconSpring = { type: "spring" as const, stiffness: 560, damping: 28, mass: 0.55 };

export function MobileTabBar() {
  const pathname = usePathname();

  return (
    <div className="fixed inset-x-0 bottom-0 z-40 pointer-events-none lg:hidden" aria-hidden={false}>
      {/* Bottom scrim — dims content behind nav for legibility */}
      <div className="mobile-nav-scrim" aria-hidden="true" />

      <nav className="relative px-safe pb-safe-or-4 pt-2" aria-label="Main navigation">
        <LayoutGroup id="mobile-tab-bar">
          <div className="mobile-nav-glass pointer-events-auto mx-auto flex max-w-[22.5rem] items-stretch">
            {MOBILE_NAV_ITEMS.map((item) => {
              const active = isMobileNavActive(pathname, item);
              const Icon = item.icon;

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className="relative flex min-w-0 flex-1 flex-col items-center justify-center rounded-full px-0.5 py-1.5 outline-none focus-visible:ring-2 focus-visible:ring-[var(--ios-tab-active)] focus-visible:ring-offset-2"
                >
                  {active && (
                    <motion.span
                      layoutId="mobile-tab-active-pill"
                      className="mobile-nav-tab-active-pill absolute inset-x-0.5 inset-y-0.5"
                      transition={tabSpring}
                    />
                  )}

                  <motion.span
                    className="relative z-10 flex min-h-[2.75rem] flex-col items-center justify-center gap-[0.2rem]"
                    animate={{ scale: active ? 1 : 0.96 }}
                    whileTap={{ scale: 0.88 }}
                    transition={iconSpring}
                  >
                    <motion.span
                      animate={{
                        y: active ? -0.5 : 0,
                      }}
                      transition={tabSpring}
                    >
                      <Icon
                        className={cn(
                          "h-[1.35rem] w-[1.35rem] transition-colors duration-300 ease-out",
                          active
                            ? "text-[var(--ios-tab-active)] dark:text-[var(--ios-tab-active-dark)]"
                            : "text-[rgb(142_142_147)] dark:text-[rgb(152_152_157)]",
                        )}
                        strokeWidth={active ? 2.4 : 1.65}
                      />
                    </motion.span>

                    <motion.span
                      className={cn(
                        "max-w-full truncate text-[0.625rem] leading-none tracking-[-0.01em]",
                        active
                          ? "font-semibold text-[var(--ios-tab-active)] dark:text-[var(--ios-tab-active-dark)]"
                          : "font-medium text-[rgb(142_142_147)] dark:text-[rgb(152_152_157)]",
                      )}
                      animate={{ opacity: active ? 1 : 0.88 }}
                      transition={{ duration: 0.2 }}
                    >
                      {item.label}
                    </motion.span>
                  </motion.span>
                </Link>
              );
            })}
          </div>
        </LayoutGroup>
      </nav>
    </div>
  );
}
