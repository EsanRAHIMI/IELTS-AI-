"use client";

import { Moon, Sun, LogOut, Menu, Volume2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { useSpeech } from "@/lib/speech";
import { Button } from "@/components/ui/button";
import { Dropdown, DropdownItem } from "@/components/ui/dropdown";
import { PrepOrientation } from "@/components/prep-orientation";
import { useOrientationHidden } from "@/components/orientation-visibility";

function pageTitleClass(orientationHidden: boolean) {
  return cn(
    "min-w-0 truncate font-semibold",
    orientationHidden ? "text-lg" : "max-md:sr-only md:max-w-[9rem] md:text-base lg:max-w-[14rem] lg:text-lg",
  );
}

export function Topbar({ onMenu, title }: { onMenu: () => void; title: string }) {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const { enabled: speakOn, toggle: toggleSpeak } = useSpeech();
  const orientationHidden = useOrientationHidden();

  return (
    <header className="sticky top-0 z-30 shrink-0 border-b bg-background/95 backdrop-blur-md supports-[backdrop-filter]:bg-background/80">
      <div className="pt-safe px-safe">
        <div className="flex h-16 items-center gap-1.5 px-2 md:gap-2 md:px-4">
          <Button variant="ghost" size="icon" className="h-9 w-9 shrink-0 lg:hidden md:h-10 md:w-10" onClick={onMenu} aria-label="Menu">
            <Menu className="h-5 w-5" />
          </Button>
          <h1 className={pageTitleClass(orientationHidden)}>{title}</h1>
          <PrepOrientation />
          <div className="ml-auto flex shrink-0 items-center gap-0.5 md:gap-1">
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleSpeak}
              aria-pressed={speakOn}
              aria-label={speakOn ? "Stop reading cards aloud" : "Read cards aloud"}
              className="h-9 w-9 md:h-10 md:w-10"
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
            <Button variant="ghost" size="icon" onClick={toggle} aria-label="Toggle theme" className="h-9 w-9 md:h-10 md:w-10">
              {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            </Button>
            <Dropdown
              trigger={
                <Button variant="ghost" size="sm" className="gap-2">
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
