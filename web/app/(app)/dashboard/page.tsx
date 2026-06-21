"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import {
  BookText,
  Quote,
  Layers,
  FileStack,
  Flame,
  Trophy,
  CalendarClock,
  Target,
  ArrowRight,
} from "lucide-react";
import { useApiData } from "@/hooks/useApiData";
import type { Dashboard } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

export default function DashboardPage() {
  const { data, loading } = useApiData<Dashboard>("/dashboard");

  const stats = [
    { label: "Sources", value: data?.totalSources, icon: FileStack, href: "/import" },
    { label: "Words", value: data?.totalWords, icon: BookText, href: "/vocabulary" },
    { label: "Phrases", value: data?.totalPhrases, icon: Quote, href: "/phrases" },
    { label: "Patterns", value: data?.totalPatterns, icon: Layers, href: "/patterns" },
  ];

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {stats.map((s, i) => (
          <motion.div key={s.label} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
            <Link href={s.href}>
              <Card className="transition-shadow hover:shadow-md">
                <CardContent className="flex items-center justify-between p-6">
                  <div>
                    <p className="text-sm text-muted-foreground">{s.label}</p>
                    {loading ? <Skeleton className="mt-2 h-8 w-16" /> : <p className="mt-1 text-3xl font-bold">{s.value ?? 0}</p>}
                  </div>
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-secondary text-foreground">
                    <s.icon className="h-6 w-6" />
                  </div>
                </CardContent>
              </Card>
            </Link>
          </motion.div>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Today&apos;s study snapshot</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-3">
            <MiniStat icon={<CalendarClock className="h-5 w-5" />} label="Cards due today" value={data?.dueToday ?? 0} loading={loading} accent />
            <MiniStat icon={<Trophy className="h-5 w-5" />} label="Mastered items" value={data?.mastered ?? 0} loading={loading} />
            <MiniStat icon={<Flame className="h-5 w-5" />} label="Learning streak" value={`${data?.streak ?? 0} d`} loading={loading} />
          </CardContent>
          <CardContent className="pt-0">
            <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
              <Link href="/study" className="w-full sm:w-auto"><Button className="h-10 w-full gap-2 sm:w-auto">Start studying <ArrowRight className="h-4 w-4" /></Button></Link>
              <Link href="/daily-plan" className="w-full sm:w-auto"><Button variant="outline" className="h-10 w-full sm:w-auto">View daily plan</Button></Link>
              <Link href="/quiz" className="w-full sm:w-auto"><Button variant="outline" className="h-10 w-full sm:w-auto">Take a quiz</Button></Link>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Target className="h-5 w-5" /> Current focus</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-sm text-muted-foreground">Focus modules</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {(data?.focus || []).length ? (
                  data!.focus.map((f) => <Badge key={f} variant="secondary">{f}</Badge>)
                ) : (
                  <span className="text-sm text-muted-foreground">Set in Settings</span>
                )}
              </div>
            </div>
            <div className="flex items-center justify-between border-t pt-3 text-sm">
              <span className="text-muted-foreground">Target band</span>
              <span className="font-semibold">{data?.targetBand ?? "—"}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Exam date</span>
              <span className="font-semibold">{data?.examDate || "Not set"}</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {!loading && data && data.totalWords === 0 && (
        <Card className="border-accent/40 bg-accent/5">
          <CardContent className="flex flex-col items-start gap-3 p-6 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-semibold">Your corpus is empty.</p>
              <p className="text-sm text-muted-foreground">Import a source or seed the starter IELTS dataset to begin.</p>
            </div>
            <Link href="/import"><Button variant="accent">Go to Import Center</Button></Link>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function MiniStat({ icon, label, value, loading, accent }: { icon: React.ReactNode; label: string; value: number | string; loading: boolean; accent?: boolean }) {
  return (
    <div className={`rounded-lg border p-4 ${accent ? "border-accent/40 bg-accent/5" : ""}`}>
      <div className="mb-2 flex items-center gap-2 text-muted-foreground">{icon}<span className="text-sm">{label}</span></div>
      {loading ? <Skeleton className="h-7 w-12" /> : <p className="text-2xl font-bold">{value}</p>}
    </div>
  );
}
