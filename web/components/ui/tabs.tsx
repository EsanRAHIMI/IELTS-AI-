"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

const TabsContext = React.createContext<{ value: string; setValue: (v: string) => void }>({
  value: "",
  setValue: () => {},
});

export function Tabs({
  defaultValue,
  value: controlled,
  onValueChange,
  className,
  children,
}: {
  defaultValue?: string;
  value?: string;
  onValueChange?: (v: string) => void;
  className?: string;
  children: React.ReactNode;
}) {
  const [internal, setInternal] = React.useState(defaultValue || "");
  const value = controlled ?? internal;
  const setValue = (v: string) => {
    setInternal(v);
    onValueChange?.(v);
  };
  return (
    <TabsContext.Provider value={{ value, setValue }}>
      <div className={cn("min-w-0", className)}>{children}</div>
    </TabsContext.Provider>
  );
}

export const TabsList = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div
    className={cn(
      "flex w-full min-w-0 items-center gap-0.5 rounded-xl bg-secondary/90 p-1",
      "overflow-x-auto [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden",
      className,
    )}
    role="tablist"
    {...props}
  />
);

export function TabsTrigger({ value, className, children }: { value: string; className?: string; children: React.ReactNode }) {
  const ctx = React.useContext(TabsContext);
  const active = ctx.value === value;
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={() => ctx.setValue(value)}
      className={cn(
        "inline-flex min-h-9 min-w-0 flex-1 items-center justify-center rounded-lg px-2 py-2 text-xs font-medium transition-all sm:text-sm",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        active ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
        className,
      )}
    >
      <span className="truncate">{children}</span>
    </button>
  );
}

export function TabsContent({ value, className, children }: { value: string; className?: string; children: React.ReactNode }) {
  const ctx = React.useContext(TabsContext);
  if (ctx.value !== value) return null;
  return <div className={cn("mt-4 min-w-0 animate-fade-in", className)}>{children}</div>;
}
