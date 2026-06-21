"use client";

import { useCallback, useEffect, useState } from "react";
import {
  BeforeInstallPromptEvent,
  detectPwaPlatform,
  dismissPwaBanner,
  isMobileDevice,
  isPwaDismissed,
  isStandaloneMode,
  PwaPlatform,
} from "@/lib/pwa";

export function usePwaInstall() {
  const [installPrompt, setInstallPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [isStandalone, setIsStandalone] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [platform, setPlatform] = useState<PwaPlatform>("other");
  const [dismissed, setDismissed] = useState(false);
  const [installing, setInstalling] = useState(false);

  useEffect(() => {
    setIsStandalone(isStandaloneMode());
    setIsMobile(isMobileDevice());
    setPlatform(detectPwaPlatform());
    setDismissed(isPwaDismissed());

    const onResize = () => setIsMobile(isMobileDevice());
    window.addEventListener("resize", onResize);

    const onPrompt = (event: BeforeInstallPromptEvent) => {
      event.preventDefault();
      setInstallPrompt(event);
    };

    const onInstalled = () => {
      setInstallPrompt(null);
      setIsStandalone(true);
    };

    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);

    return () => {
      window.removeEventListener("resize", onResize);
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  const install = useCallback(async () => {
    if (!installPrompt) return false;
    setInstalling(true);
    try {
      await installPrompt.prompt();
      const { outcome } = await installPrompt.userChoice;
      setInstallPrompt(null);
      return outcome === "accepted";
    } finally {
      setInstalling(false);
    }
  }, [installPrompt]);

  const dismiss = useCallback(() => {
    dismissPwaBanner();
    setDismissed(true);
  }, []);

  const canShow = isMobile && !isStandalone && !dismissed;
  const hasNativePrompt = Boolean(installPrompt);
  const showIosInstructions = platform === "ios";
  const showAndroidInstall = platform === "android" && hasNativePrompt;

  return {
    canShow,
    platform,
    hasNativePrompt,
    showIosInstructions,
    showAndroidInstall,
    installing,
    install,
    dismiss,
  };
}
