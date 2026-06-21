"use client";

import { useEffect } from "react";
import { isStandaloneMode } from "@/lib/pwa";

/** Marks standalone/PWA mode on `<html>` for safe-area CSS fallbacks. */
export function SafeAreaRoot() {
  useEffect(() => {
    const root = document.documentElement;

    const sync = () => {
      if (isStandaloneMode()) {
        root.dataset.displayMode = "standalone";
      } else {
        delete root.dataset.displayMode;
      }
    };

    sync();
    window.matchMedia("(display-mode: standalone)").addEventListener("change", sync);
    window.addEventListener("appinstalled", sync);

    return () => {
      window.matchMedia("(display-mode: standalone)").removeEventListener("change", sync);
      window.removeEventListener("appinstalled", sync);
    };
  }, []);

  return null;
}
