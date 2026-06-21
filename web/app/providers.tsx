"use client";

import { AuthProvider } from "@/lib/auth";
import { ThemeProvider } from "@/lib/theme";
import { ToastProvider } from "@/components/ui/toast";
import { SafeAreaRoot } from "@/components/safe-area-root";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <ToastProvider>
        <AuthProvider>
          <SafeAreaRoot />
          {children}
        </AuthProvider>
      </ToastProvider>
    </ThemeProvider>
  );
}
