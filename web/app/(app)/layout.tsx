"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";
import { Sheet } from "@/components/ui/sheet";
import { PwaInstallBanner } from "@/components/pwa-install-banner";
import { PwaInstallProvider, usePwaInstallContext } from "@/components/pwa-install-provider";

const TITLES: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/import": "Import Center",
  "/vocabulary": "Vocabulary Ranker",
  "/phrases": "Phrases & Collocations",
  "/patterns": "Sentence Patterns",
  "/study": "Study Mode",
  "/daily-plan": "Daily Plan",
  "/quiz": "Quiz Mode",
  "/progress": "Progress",
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
    <div className="flex min-h-[100dvh] overflow-hidden">
      <aside className="hidden w-64 shrink-0 border-r bg-card lg:block">
        <Sidebar />
      </aside>
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen} side="left" className="max-w-[16rem] p-0">
        <Sidebar onNavigate={() => setMobileOpen(false)} />
      </Sheet>
      <div className="flex min-h-[100dvh] flex-1 flex-col overflow-hidden">
        <Topbar onMenu={() => setMobileOpen(true)} title={title} />
        <main className={`flex-1 overflow-y-auto p-4 md:p-6 lg:p-8 ${showPwaBanner ? "pb-36 md:pb-8" : "pb-safe"}`}>
          {children}
        </main>
        <PwaInstallBanner />
      </div>
    </div>
  );
}
