"use client";

import { useCallback, useState } from "react";
import { AlertCircle, CheckCircle2, Loader2, X } from "lucide-react";
import { cn } from "@/lib/utils";

export type WorkPhase = "progress" | "success" | "error";

export interface WorkNotice {
  phase: WorkPhase;
  title: string;
  detail?: string;
}

const PHASE_LABEL: Record<WorkPhase, string> = {
  progress: "In progress",
  success: "Finished",
  error: "Failed",
};

export function workError(err: unknown, fallback = "Something went wrong. Try again.") {
  return err instanceof Error && err.message ? err.message : fallback;
}

export function WorkStatus({
  phase,
  title,
  detail,
  onDismiss,
  compact = false,
  className,
}: WorkNotice & {
  onDismiss?: () => void;
  compact?: boolean;
  className?: string;
}) {
  const Icon = phase === "progress" ? Loader2 : phase === "success" ? CheckCircle2 : AlertCircle;

  return (
    <div
      role={phase === "error" ? "alert" : "status"}
      aria-live={phase === "error" ? "assertive" : "polite"}
      className={cn(
        "flex items-start gap-3 rounded-lg border",
        compact ? "px-3 py-2" : "px-3.5 py-3",
        phase === "progress" && "border-accent/40 bg-accent/10",
        phase === "success" && "border-success/40 bg-success/10",
        phase === "error" && "border-destructive/40 bg-destructive/10",
        className,
      )}
    >
      <Icon
        className={cn(
          "mt-0.5 shrink-0",
          compact ? "h-4 w-4" : "h-5 w-5",
          phase === "progress" && "animate-spin text-accent",
          phase === "success" && "text-success",
          phase === "error" && "text-destructive",
        )}
        aria-hidden
      />
      <div className="min-w-0 flex-1">
        <p className="section-label">{PHASE_LABEL[phase]}</p>
        <p className={cn("font-medium leading-snug", compact ? "text-sm" : "text-sm")}>{title}</p>
        {detail && <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{detail}</p>}
      </div>
      {onDismiss && phase !== "progress" && (
        <button
          type="button"
          onClick={onDismiss}
          className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-muted-foreground hover:bg-secondary hover:text-foreground lg:h-8 lg:w-8"
          aria-label="Dismiss status"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}

/** Run one action and keep its in-progress, finished, or failed state on screen. */
export function useWorkNotice() {
  const [notice, setNotice] = useState<WorkNotice | null>(null);

  const run = useCallback(async (progress: string, task: () => Promise<void>, success: string) => {
    setNotice({ phase: "progress", title: progress });
    try {
      await task();
      setNotice({ phase: "success", title: success });
    } catch (err) {
      setNotice({ phase: "error", title: "Could not finish", detail: workError(err) });
    }
  }, []);

  return { notice, setNotice, run };
}
