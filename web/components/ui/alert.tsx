import * as React from "react";
import { AlertCircle, CheckCircle2, Info, X } from "lucide-react";
import { cn } from "@/lib/utils";

type AlertVariant = "error" | "success" | "info";

export function Alert({
  variant = "info",
  title,
  children,
  hint,
  onDismiss,
  className,
}: {
  variant?: AlertVariant;
  title: string;
  children?: React.ReactNode;
  hint?: string;
  onDismiss?: () => void;
  className?: string;
}) {
  const Icon = variant === "error" ? AlertCircle : variant === "success" ? CheckCircle2 : Info;

  return (
    <div
      role="alert"
      className={cn(
        "relative rounded-lg border p-4 text-sm",
        variant === "error" && "border-destructive/30 bg-destructive/5 text-foreground",
        variant === "success" && "border-success/30 bg-success/5",
        variant === "info" && "border-border bg-muted/40",
        className,
      )}
    >
      <div className="flex gap-3">
        <Icon
          className={cn(
            "mt-0.5 h-5 w-5 shrink-0",
            variant === "error" && "text-destructive",
            variant === "success" && "text-success",
            variant === "info" && "text-muted-foreground",
          )}
        />
        <div className="min-w-0 flex-1 space-y-1">
          <p className="font-semibold leading-snug">{title}</p>
          {children && <p className="text-muted-foreground leading-relaxed">{children}</p>}
          {hint && <p className="text-xs text-muted-foreground/90 leading-relaxed">{hint}</p>}
        </div>
        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            className="shrink-0 text-muted-foreground hover:text-foreground"
            aria-label="Dismiss"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
}

export function FieldError({ id, message }: { id?: string; message?: string }) {
  if (!message || message.trim() === "") return null;
  return (
    <p id={id} role="alert" className="text-xs font-medium text-destructive">
      {message}
    </p>
  );
}
