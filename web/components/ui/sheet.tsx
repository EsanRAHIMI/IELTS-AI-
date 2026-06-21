"use client";

import * as React from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

export function Sheet({
  open,
  onOpenChange,
  children,
  side = "right",
  className,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  children: React.ReactNode;
  side?: "right" | "left";
  className?: string;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/50 animate-fade-in" onClick={() => onOpenChange(false)} />
      <div
        className={cn(
          "absolute top-0 flex h-full w-full max-w-md flex-col overflow-y-auto border-l bg-card shadow-xl animate-fade-in pt-safe pb-safe px-safe",
          side === "right" ? "right-0 border-l" : "left-0 border-r",
          className,
        )}
      >
        <button
          className="absolute right-4 z-10 text-muted-foreground hover:text-foreground"
          style={{ top: "calc(1rem + var(--safe-top))" }}
          onClick={() => onOpenChange(false)}
          aria-label="Close"
        >
          <X className="h-5 w-5" />
        </button>
        {children}
      </div>
    </div>
  );
}

/** Default padded content wrapper for sheets */
export function SheetBody({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn("min-w-0 p-4 pt-14", className)}>{children}</div>;
}
