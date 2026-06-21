"use client";

import Link from "next/link";
import { Clock, BookText, Quote, Layers, CalendarClock, Plus } from "lucide-react";
import { api } from "@/lib/api";
import { useApiData } from "@/hooks/useApiData";
import type { Word, Phrase, Pattern } from "@/types";
import { cn, priorityColor } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";

interface Plan {
  date: string;
  words: Word[];
  phrases: Phrase[];
  patterns: Pattern[];
  dueCards: number;
  estimatedMinutes: number;
}

export default function DailyPlanPage() {
  const { toast } = useToast();
  const { data, loading } = useApiData<Plan>("/study/daily-plan");

  async function addAll(type: string, items: { id: string }[]) {
    await Promise.all(items.map((i) => api("/study/cards", { method: "POST", body: { type, refId: i.id } }).catch(() => {})));
    toast({ title: "Added to study", variant: "success" });
  }

  if (loading) return <p className="text-sm text-muted-foreground">Building your plan…</p>;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <Card className="border-accent/40 bg-accent/5">
          <CardContent className="flex items-center gap-3 p-5">
            <Clock className="h-8 w-8 text-accent" />
            <div><p className="text-2xl font-bold">{data.estimatedMinutes} min</p><p className="text-sm text-muted-foreground">Estimated time</p></div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 p-5">
            <CalendarClock className="h-8 w-8 text-muted-foreground" />
            <div><p className="text-2xl font-bold">{data.dueCards}</p><p className="text-sm text-muted-foreground">Cards due for review</p></div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
            <div><p className="text-sm text-muted-foreground">Ready to go?</p><p className="font-semibold">Start your session</p></div>
            <Link href="/study" className="w-full sm:w-auto"><Button className="h-10 w-full sm:w-auto">Study now</Button></Link>
          </CardContent>
        </Card>
      </div>

      <PlanSection title="Top 30 words" icon={<BookText className="h-5 w-5" />} count={data.words.length} onAdd={() => addAll("word", data.words)}>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {data.words.map((w) => (
            <div key={w.id} className="flex items-center justify-between gap-2 rounded-md border p-2.5">
              <div className="min-w-0">
                <p className="truncate font-medium">{w.word}</p>
                {w.persianMeaning && <p className="farsi truncate text-xs text-muted-foreground">{w.persianMeaning}</p>}
              </div>
              <span className={cn("inline-flex h-6 w-8 shrink-0 items-center justify-center rounded text-xs font-bold", priorityColor(w.priorityScore))}>{w.priorityScore}</span>
            </div>
          ))}
        </div>
      </PlanSection>

      <PlanSection title="Top 15 phrases" icon={<Quote className="h-5 w-5" />} count={data.phrases.length} onAdd={() => addAll("phrase", data.phrases)}>
        <div className="grid gap-2 sm:grid-cols-2">
          {data.phrases.map((p) => (
            <div key={p.id} className="rounded-md border p-2.5">
              <p className="font-medium">{p.phrase}</p>
              <Badge variant="secondary" className="mt-1 text-[10px]">{p.section}</Badge>
            </div>
          ))}
        </div>
      </PlanSection>

      <PlanSection title="Top 10 sentence patterns" icon={<Layers className="h-5 w-5" />} count={data.patterns.length} onAdd={() => addAll("sentence_pattern", data.patterns)}>
        <div className="space-y-2">
          {data.patterns.map((p) => (
            <div key={p.id} className="rounded-md border p-2.5">
              <Badge variant="accent" className="mb-1 text-[10px]">{p.category}</Badge>
              <p className="text-sm">{p.template}</p>
            </div>
          ))}
        </div>
      </PlanSection>
    </div>
  );
}

function PlanSection({ title, icon, count, onAdd, children }: { title: string; icon: React.ReactNode; count: number; onAdd: () => void; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader className="flex flex-col gap-3 space-y-0 sm:flex-row sm:items-center sm:justify-between">
        <CardTitle className="flex flex-wrap items-center gap-2 text-base sm:text-lg">{icon} {title} <Badge variant="muted">{count}</Badge></CardTitle>
        {count > 0 && <Button size="sm" variant="outline" className="h-9 w-full gap-1.5 sm:w-auto" onClick={onAdd}><Plus className="h-3.5 w-3.5" /> Add all</Button>}
      </CardHeader>
      <CardContent>{count ? children : <p className="text-sm text-muted-foreground">Nothing here yet — import sources or seed data.</p>}</CardContent>
    </Card>
  );
}
