"use client";

import { useLayoutEffect, useRef } from "react";
import { Moon, Sun, LogOut, Menu, Volume2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { useSpeech } from "@/lib/speech";
import { Button } from "@/components/ui/button";
import { Dropdown, DropdownItem } from "@/components/ui/dropdown";
import { PrepOrientation } from "@/components/prep-orientation";
import { useOrientationHidden } from "@/components/orientation-visibility";

export function Topbar({ onMenu, title }: { onMenu: () => void; title: string }) {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const { enabled: speakOn, toggle: toggleSpeak } = useSpeech();
  const orientationHidden = useOrientationHidden();
  const headerRef = useRef<HTMLElement>(null);

  useLayoutEffect(() => {
    const el = headerRef.current;
    if (!el) return;
    const apply = () => {
      document.documentElement.style.setProperty(
        "--app-topbar-height",
        `${Math.ceil(el.getBoundingClientRect().height)}px`,
      );
    };
    apply();
    const observer = new ResizeObserver(apply);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <header
      ref={headerRef}
      className="sticky top-0 z-30 shrink-0 border-b bg-background/95 backdrop-blur-md supports-[backdrop-filter]:bg-background/80"
    >
      <div className="pt-safe px-safe">
        <div className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-1.5 gap-y-1 px-2 pb-2 pt-1.5 lg:flex lg:h-16 lg:items-center lg:gap-2 lg:px-4 lg:py-0">
          <Button
            variant="ghost"
            size="icon"
            className="h-11 w-11 shrink-0 lg:hidden"
            onClick={onMenu}
            aria-label="Menu"
          >
            <Menu className="h-5 w-5" />
          </Button>
          <h1 className="min-w-0 truncate text-base font-semibold lg:max-w-[14rem]">{title}</h1>
          <div
            className={cn(
              "col-span-3 min-w-0 lg:col-auto lg:min-w-0 lg:flex-1",
              orientationHidden ? "hidden" : "lg:flex",
            )}
          >
            <PrepOrientation />
          </div>
          <div className="col-start-3 row-start-1 flex shrink-0 items-center gap-0.5 lg:col-auto lg:row-auto lg:gap-1">
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleSpeak}
              aria-pressed={speakOn}
              aria-label={speakOn ? "Stop reading cards aloud" : "Read cards aloud"}
              className="h-11 w-11 lg:h-9 lg:w-9"
            >
              <span className="relative inline-flex">
                <Volume2 className="h-5 w-5" />
                {!speakOn && (
                  <span
                    aria-hidden
                    className="pointer-events-none absolute left-1/2 top-1/2 h-0.5 w-5 -translate-x-1/2 -translate-y-1/2 rotate-45 rounded-full bg-current"
                  />
                )}
              </span>
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={toggle}
              aria-label="Toggle theme"
              className="h-11 w-11 lg:h-9 lg:w-9"
            >
              {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            </Button>
            <Dropdown
              trigger={
                <Button variant="ghost" size="sm" className="h-11 gap-2 px-2 lg:h-9">
                  <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
                    {(user?.name || user?.email || "?").charAt(0).toUpperCase()}
                  </span>
                  <span className="hidden max-w-[140px] truncate sm:inline">{user?.name || user?.email}</span>
                </Button>
              }
            >
              <div className="px-3 py-2 text-xs text-muted-foreground">{user?.email}</div>
              <DropdownItem onClick={logout}>
                <LogOut className="h-4 w-4" /> Log out
              </DropdownItem>
            </Dropdown>
          </div>
        </div>
      </div>
    </header>
  );
}
