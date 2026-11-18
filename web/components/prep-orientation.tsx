"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { api } from "@/lib/api";
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
  const showAction = Boolean(action) && pathname !== "/dashboard";

  if (hidden) return null;

  return (
    <section
      aria-label="Where you are"
      data-prep-stage={step?.stage ?? (failed ? "error" : "loading")}
      className="flex w-full min-w-0 items-center gap-2"
    >
      <time dateTime={clock.iso || undefined} data-local-time className="shrink-0 text-sm font-semibold tabular-nums">
        {clock.time || "—"}
        {clock.zone ? <span className="ml-1 hidden font-medium text-muted-foreground sm:inline"> {clock.zone}</span> : null}
      </time>
      <span className="min-w-0 flex-1 truncate text-sm font-semibold">{label}</span>
      {showAction ? (
        <Link
          href={href}
          title={detail}
          aria-label={`${action}. ${detail}`}
          data-orientation-action=""
          className="ml-auto inline-flex h-11 max-w-[11rem] shrink-0 items-center truncate rounded-lg bg-primary px-3 text-sm font-medium text-primary-foreground lg:h-9 lg:max-w-[14rem]"
        >
          {action}
        </Link>
      ) : null}
    </section>
  );
}
