"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { useOrientationHidden } from "@/components/orientation-visibility";

type PrepStep = {
  stage: string;
  stageLabel: string;
  action: string;
  detail: string;
  href: string;
};

function useLocalClock() {
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    const tick = () => setNow(new Date());
    tick();
    const id = window.setInterval(tick, 15000);
    return () => window.clearInterval(id);
  }, []);

  if (!now) return { time: "", zone: "", iso: "" };
  const time = new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
  }).format(now);
  const zone =
    new Intl.DateTimeFormat(undefined, { timeZoneName: "short" })
      .formatToParts(now)
      .find((part) => part.type === "timeZoneName")?.value ?? "";
  return { time, zone, iso: now.toISOString() };
}

export function PrepOrientation() {
  const pathname = usePathname();
  const clock = useLocalClock();
  const [step, setStep] = useState<PrepStep | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api<PrepStep>("/orientation")
      .then((next) => {
        if (cancelled) return;
        setStep(next);
        setFailed(false);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [pathname]);

  useEffect(() => {
    const id = window.setInterval(() => {
      api<PrepStep>("/orientation")
        .then((next) => {
          setStep(next);
          setFailed(false);
        })
        .catch(() => {
          /* Keep the last stage if a refresh fails. */
        });
    }, 60000);
    return () => window.clearInterval(id);
  }, []);

  const label = step?.stageLabel ?? (failed ? "Unavailable" : "Checking progress");
  const detail = step?.detail ?? (
    failed
      ? "Your progress could not be read. The clock is still your local time."
      : "Reading what you have already saved."
  );
  const action = step?.action ?? (failed ? "Open home" : "");
  const href = step?.href ?? "/dashboard";
  const hidden = useOrientationHidden();

  if (hidden) return null;

  return (
    <section
      aria-label="Where you are"
      data-prep-stage={step?.stage ?? (failed ? "error" : "loading")}
      className="shrink-0 border-b bg-card px-page py-2.5 md:px-6 lg:px-8"
    >
      <div className="mx-auto flex max-w-6xl flex-col gap-2 sm:flex-row sm:items-center sm:gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <div className="shrink-0">
            <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Local time</p>
            <time dateTime={clock.iso || undefined} data-local-time className="text-sm font-semibold tabular-nums">
              {clock.time || "—"}
              {clock.zone ? <span className="ml-1.5 text-xs font-medium text-muted-foreground"> {clock.zone}</span> : null}
            </time>
          </div>
          <span className="h-8 w-px shrink-0 bg-border" aria-hidden />
          <div className="min-w-0">
            <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Stage</p>
            <p className="truncate text-sm font-semibold">{label}</p>
          </div>
        </div>
        <p className="min-w-0 flex-1 text-xs leading-5 text-muted-foreground sm:text-right">{detail}</p>
        {action ? (
          <Link href={href} className="shrink-0">
            <Button size="sm" className="w-full sm:w-auto">{action}</Button>
          </Link>
        ) : null}
      </div>
    </section>
  );
}
