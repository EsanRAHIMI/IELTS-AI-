"use client";

import { Download, Share, Smartphone, X } from "lucide-react";
import { usePwaInstallContext } from "@/components/pwa-install-provider";
import { Button } from "@/components/ui/button";

export function PwaInstallBanner() {
  const {
    canShow,
    platform,
    showIosInstructions,
    showAndroidInstall,
    hasNativePrompt,
    installing,
    install,
    dismiss,
  } = usePwaInstallContext();

  if (!canShow) return null;

  return (
    <div
      className="fixed inset-x-0 z-30 border-t bg-card/95 px-safe shadow-[0_-8px_30px_rgba(0,0,0,0.12)] backdrop-blur-md lg:hidden"
      style={{ bottom: "var(--mobile-tab-bar-offset)" }}
      role="region"
      aria-label="Install app"
    >
      <div className="mx-auto max-w-lg p-4 pb-safe-or-4">
        <div className="flex items-start gap-3">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-accent/15 text-accent">
          <Smartphone className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-semibold leading-tight">Install IELTS Mastery</p>
          {showIosInstructions ? (
            <p className="mt-1 text-sm text-muted-foreground">
              Tap <Share className="mx-0.5 inline h-3.5 w-3.5 align-text-bottom" /> Share, then{" "}
              <span className="font-medium text-foreground">Add to Home Screen</span> for full-screen access.
            </p>
          ) : showAndroidInstall ? (
            <p className="mt-1 text-sm text-muted-foreground">
              Install the app for faster access and a native-like experience on your phone.
            </p>
          ) : (
            <p className="mt-1 text-sm text-muted-foreground">
              {platform === "android"
                ? "Open browser menu and choose Install app, or wait until the install prompt is ready."
                : "Add this app to your home screen for the best mobile experience."}
            </p>
          )}
          <div className="mt-3 flex flex-wrap gap-2">
            {showAndroidInstall && (
              <Button size="sm" className="gap-2" onClick={() => void install()} disabled={installing || !hasNativePrompt}>
                <Download className="h-4 w-4" />
                {installing ? "Installing…" : "Install app"}
              </Button>
            )}
            <Button size="sm" variant="outline" onClick={dismiss}>
              Not now
            </Button>
          </div>
        </div>
        <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0" onClick={dismiss} aria-label="Dismiss">
          <X className="h-4 w-4" />
        </Button>
        </div>
      </div>
    </div>
  );
}
