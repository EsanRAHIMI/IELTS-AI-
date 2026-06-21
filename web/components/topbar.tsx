"use client";

import { Moon, Sun, LogOut, Menu } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { Button } from "@/components/ui/button";
import { Dropdown, DropdownItem } from "@/components/ui/dropdown";

export function Topbar({ onMenu, title }: { onMenu: () => void; title: string }) {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();

  return (
    <header className="sticky top-0 z-30 shrink-0 border-b bg-background/95 backdrop-blur-md supports-[backdrop-filter]:bg-background/80">
      <div className="pt-safe px-safe">
        <div className="flex h-16 items-center justify-between gap-3 px-4 md:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <Button variant="ghost" size="icon" className="shrink-0 lg:hidden" onClick={onMenu} aria-label="Menu">
              <Menu className="h-5 w-5" />
            </Button>
            <h1 className="truncate text-lg font-semibold md:text-xl">{title}</h1>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <Button variant="ghost" size="icon" onClick={toggle} aria-label="Toggle theme">
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
