"use client";

import { createContext, useContext } from "react";
import { usePwaInstall } from "@/hooks/usePwaInstall";

type PwaInstallContextValue = ReturnType<typeof usePwaInstall>;

const PwaInstallContext = createContext<PwaInstallContextValue | null>(null);

export function PwaInstallProvider({ children }: { children: React.ReactNode }) {
  const value = usePwaInstall();
  return <PwaInstallContext.Provider value={value}>{children}</PwaInstallContext.Provider>;
}

export function usePwaInstallContext() {
  const ctx = useContext(PwaInstallContext);
  if (!ctx) throw new Error("usePwaInstallContext must be used within PwaInstallProvider");
  return ctx;
}
