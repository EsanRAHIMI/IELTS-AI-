"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";
import { Sheet } from "@/components/ui/sheet";
import { PwaInstallBanner } from "@/components/pwa-install-banner";
import { PwaInstallProvider, usePwaInstallContext } from "@/components/pwa-install-provider";
import { MobileTabBar } from "@/components/mobile-tab-bar";
import { OrientationVisibility } from "@/components/orientation-visibility";

const TITLES: Record<string, string> = {
  "/dashboard": "Home",
  "/import": "Sources",
  "/vocabulary": "Words",
  "/phrases": "Phrases",
  "/patterns": "Patterns",
  "/study": "Study",
  "/daily-plan": "Daily plan",
  "/quiz": "Quiz",
  "/progress": "Stats",
  "/settings": "Settings",
};

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.replace("/");
  }, [user, loading, router]);

  if (loading || !user) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-muted border-t-primary" />
      </div>
    );
  }

  const title = TITLES[pathname] || Object.entries(TITLES).find(([k]) => pathname.startsWith(k))?.[1] || "IELTS Mastery";

  return (
    <PwaInstallProvider>
      <AppShell title={title} mobileOpen={mobileOpen} setMobileOpen={setMobileOpen}>
        {children}
      </AppShell>
    </PwaInstallProvider>
  );
}

function AppShell({
  children,
  title,
  mobileOpen,
  setMobileOpen,
}: {
  children: React.ReactNode;
  title: string;
  mobileOpen: boolean;
  setMobileOpen: (open: boolean) => void;
}) {
  const { canShow: showPwaBanner } = usePwaInstallContext();

  return (
    <div className="flex h-dvh overflow-hidden">
      <aside className="hidden w-64 shrink-0 border-r bg-card lg:block">
        <Sidebar />
      </aside>
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen} side="left" className="max-w-[16rem] p-0">
        <Sidebar onNavigate={() => setMobileOpen(false)} />
      </Sheet>
      <div className="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <OrientationVisibility>
          <Topbar onMenu={() => setMobileOpen(true)} title={title} />
          <main
            className={cn(
              "min-h-0 flex-1 overflow-y-auto overflow-x-clip px-page py-4 md:px-6 md:py-6 lg:px-8 lg:py-6",
              showPwaBanner
                ? "mb-[calc(var(--tab-bar-clearance)+7.5rem)]"
                : "mb-[var(--tab-bar-clearance)]",
            )}
          >
            <div className="mx-auto min-w-0 max-w-6xl">{children}</div>
          </main>
          <PwaInstallBanner />
          <MobileTabBar />
        </OrientationVisibility>
      </div>
    </div>
  );
}
