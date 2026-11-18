"use client";

import * as React from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

export function Dialog({
  open,
  onOpenChange,
  children,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  children: React.ReactNode;
}) {
  React.useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onOpenChange(false);
    }
    if (open) document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onOpenChange]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center p-4 pb-[var(--content-bottom-offset)] sm:items-center sm:p-4">
      <div className="absolute inset-0 bg-black/50 animate-fade-in" onClick={() => onOpenChange(false)} />
      <div
        className={cn(
          "relative z-10 flex max-h-[min(90dvh,720px)] w-full flex-col",
          "animate-fade-in rounded-lg border bg-card shadow-lg sm:max-w-lg",
        )}
      >
        <button
          className="absolute right-2 top-2 z-10 inline-flex h-11 w-11 items-center justify-center rounded-lg text-muted-foreground hover:bg-secondary hover:text-foreground"
          onClick={() => onOpenChange(false)}
          aria-label="Close"
        >
          <X className="h-5 w-5" />
        </button>
        <div className="overflow-y-auto overscroll-contain p-4 pt-12">{children}</div>
      </div>
    </div>
  );
}

export const DialogHeader = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("mb-4 space-y-1.5 pr-8", className)} {...props} />
);
export const DialogTitle = ({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => (
  <h2 className={cn("text-lg font-semibold sm:text-xl", className)} {...props} />
);
export const DialogDescription = ({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) => (
  <p className={cn("text-sm text-muted-foreground", className)} {...props} />
);
