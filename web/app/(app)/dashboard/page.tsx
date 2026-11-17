"use client";

import Link from "next/link";
import { useApiData } from "@/hooks/useApiData";
import type { Dashboard } from "@/types";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const CHOICES = [
  { href: "/study", label: "Study" },
  { href: "/daily-plan", label: "Daily plan" },
  { href: "/quiz", label: "Quiz" },
];

type PrepStep = {
  stage: string;
  stageLabel: string;
  action: string;
  detail: string;
  href: string;
};

type ExamFact = { label: string; value: string };

function parseExam(value: string | null | undefined): { label: string; days: number } | null {
  if (!value) return null;
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const exam = new Date(year, month - 1, day);
  if (exam.getFullYear() !== year || exam.getMonth() !== month - 1 || exam.getDate() !== day) return null;
  const today = new Date();
  const start = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const days = Math.round((exam.getTime() - start.getTime()) / 86400000);
  return { label: `${day} ${MONTHS[month - 1]} ${year}`, days };
}

function whereFacts(data: Dashboard): ExamFact[] {
  const facts: ExamFact[] = [];
  if (typeof data.targetBand === "number") facts.push({ label: "Target band", value: String(data.targetBand) });
  const exam = parseExam(data.examDate);
  if (!exam) return facts;
  facts.push({ label: "Exam", value: exam.label });
  if (exam.days > 1) facts.push({ label: "Days left", value: `${exam.days} days` });
  else if (exam.days === 1) facts.push({ label: "Days left", value: "1 day" });
  else if (exam.days === 0) facts.push({ label: "Days left", value: "Today" });
  else facts.push({ label: "Days left", value: "Passed" });
  return facts;
}

function countLabel(count: number, one: string, many: string) {
  return `${count} ${count === 1 ? one : many}`;
}

export default function DashboardPage() {
  const { data, loading, error } = useApiData<Dashboard>("/dashboard");
  const { data: step, loading: stepLoading } = useApiData<PrepStep>("/orientation");

  if (loading || stepLoading) {
    return (
      <div className="grid gap-3 lg:grid-cols-3">
        <Skeleton className="h-16 lg:col-span-3" />
        <Skeleton className="h-28" />
        <Skeleton className="h-28" />
        <Skeleton className="h-28" />
      </div>
    );
  }

  if (error || !data) {
    return <p className="text-sm text-destructive">{error || "Could not read your progress."}</p>;
  }

  const facts = whereFacts(data);
  const library = data.library ?? data.totalWords + data.totalPhrases + data.totalPatterns;
  const studied = data.studied ?? data.learning + data.mastered;
  const names = data.sourceNames ?? [];
  const extraSources = data.moreSources ?? 0;
  const statuses = [
    { label: "New", value: data.cardsNew ?? 0 },
    { label: "Learning", value: data.learning },
    { label: "Due", value: data.dueToday },
    { label: "Mastered", value: data.mastered },
  ];
  const primary = step?.action && step.href ? step : null;
  const others = CHOICES.filter((choice) => choice.href !== primary?.href);
  const studiedShare = library > 0 ? Math.min(100, Math.round((studied / library) * 100)) : null;

  return (
    <div className="grid gap-3 pb-8 lg:grid-cols-3 lg:items-start">
      {facts.length > 0 && (
        <section aria-label="Where you are" data-home-where className="lg:col-span-3">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Where you are</h2>
          <dl className="mt-2 grid grid-cols-3 gap-2">
            {facts.map((fact) => (
              <div key={fact.label} className="min-w-0 rounded-lg border px-3 py-2">
                <dt className="truncate text-[11px] text-muted-foreground">{fact.label}</dt>
                <dd className="truncate text-sm font-semibold">{fact.value}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      <section aria-label="Library" data-home-library className="rounded-lg border p-3">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Library</h2>
        <p className="mt-2 text-sm leading-6">
          <Link href="/import" className="whitespace-nowrap font-medium underline-offset-2 hover:underline">{countLabel(data.totalSources, "source", "sources")}</Link>
          <span className="text-muted-foreground"> · </span>
          <Link href="/vocabulary" className="whitespace-nowrap font-medium underline-offset-2 hover:underline">{countLabel(data.totalWords, "word", "words")}</Link>
          <span className="text-muted-foreground"> · </span>
          <Link href="/phrases" className="whitespace-nowrap font-medium underline-offset-2 hover:underline">{countLabel(data.totalPhrases, "phrase", "phrases")}</Link>
          <span className="text-muted-foreground"> · </span>
          <Link href="/patterns" className="whitespace-nowrap font-medium underline-offset-2 hover:underline">{countLabel(data.totalPatterns, "pattern", "patterns")}</Link>
        </p>
        {names.length > 0 && (
          <p className="mt-2 text-sm leading-5 text-muted-foreground">
            {names.join(" · ")}
            {extraSources > 0 ? ` · +${extraSources} more` : ""}
          </p>
        )}
      </section>

      <section aria-label="Progress" data-home-progress className="rounded-lg border p-3">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Progress</h2>
        <ul className="mt-2 grid grid-cols-4 gap-1 text-center">
          {statuses.map((status) => (
            <li key={status.label} className="min-w-0">
              <span className="block text-base font-semibold tabular-nums">{status.value}</span>
              <span className="block truncate text-[11px] text-muted-foreground">{status.label}</span>
            </li>
          ))}
        </ul>
        {studiedShare !== null && (
          <div className="mt-3">
            <p className="text-sm">Studied {studied} of {library}</p>
            <div
              className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-secondary"
              role="img"
              aria-label={`Studied ${studied} of ${library}`}
            >
              <div className="h-full bg-primary" style={{ width: `${studiedShare}%` }} />
            </div>
          </div>
        )}
      </section>

      <section aria-label="What to do now" data-home-next className="rounded-lg border p-3">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Next</h2>
        {primary?.detail && <p className="mt-2 line-clamp-3 text-xs leading-5 text-muted-foreground">{primary.detail}</p>}
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {primary && (
            <Link href={primary.href}>
              <Button className="h-9">{primary.action}</Button>
            </Link>
          )}
          {others.map((choice) => (
            <Link key={choice.href} href={choice.href}>
              <Button variant="outline" className="h-9">{choice.label}</Button>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
