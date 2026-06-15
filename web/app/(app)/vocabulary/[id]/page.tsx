"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Plus, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { useApiData } from "@/hooks/useApiData";
import type { Word } from "@/types";
import { cn, priorityColor } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";

export default function WordDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { toast } = useToast();
  const { data: word, loading, reload } = useApiData<Word>(id ? `/vocabulary/${id}` : null);
  const [busy, setBusy] = useState(false);

  async function addToStudy() {
    await api("/study/cards", { method: "POST", body: { type: "word", refId: id } });
    toast({ title: "Added to flashcards", variant: "success" });
  }
  async function regenerate() {
    setBusy(true);
    try {
      await api(`/vocabulary/${id}/regenerate`, { method: "POST" });
      toast({ title: "Regenerated", variant: "success" });
      reload();
    } finally { setBusy(false); }
  }

  if (loading) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (!word) return <p className="text-sm text-muted-foreground">Word not found.</p>;

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <Button variant="ghost" size="sm" className="gap-2" onClick={() => router.push("/vocabulary")}><ArrowLeft className="h-4 w-4" /> Back to ranker</Button>

      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <div>
            <div className="flex items-center gap-2">
              <CardTitle className="text-3xl">{word.word}</CardTitle>
              <Badge variant="outline">{word.partOfSpeech}</Badge>
              <Badge variant="outline">{word.difficulty}</Badge>
            </div>
            <span className={cn("mt-2 inline-flex items-center rounded-md px-2 py-0.5 text-xs font-bold", priorityColor(word.priorityScore))}>Priority {word.priorityScore} · freq {word.frequency}</span>
          </div>
          <div className="flex gap-2">
            <Button onClick={addToStudy} className="gap-2"><Plus className="h-4 w-4" /> Study</Button>
            <Button variant="outline" onClick={regenerate} disabled={busy} className="gap-2"><RefreshCw className={cn("h-4 w-4", busy && "animate-spin")} /> Regenerate</Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-5">
          {word.persianMeaning && <Field label="Persian meaning"><p className="farsi text-lg">{word.persianMeaning}</p></Field>}
          {word.simpleEnglishMeaning && <Field label="Simple English meaning"><p>{word.simpleEnglishMeaning}</p></Field>}
          {!!word.collocations?.length && <Field label="Collocations"><div className="flex flex-wrap gap-2">{word.collocations.map((c) => <Badge key={c} variant="secondary">{c}</Badge>)}</div></Field>}
          {!!word.examples?.length && <Field label="Examples"><ul className="space-y-1.5">{word.examples.map((e, i) => <li key={i} className="rounded-md bg-secondary/50 p-2 text-sm">{e}</li>)}</ul></Field>}
          {!!word.ieltsUseCases?.length && <Field label="IELTS use cases"><div className="flex flex-wrap gap-2">{word.ieltsUseCases.map((u) => <Badge key={u} variant="accent">{u}</Badge>)}</div></Field>}
          {!!word.commonMistakes?.length && <Field label="Common mistakes"><ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">{word.commonMistakes.map((m, i) => <li key={i}>{m}</li>)}</ul></Field>}
          {word.notes && <Field label="AI study notes"><p className="text-sm text-muted-foreground">{word.notes}</p></Field>}
          {!!word.sources?.length && <Field label="Source snippets"><div className="flex flex-wrap gap-2">{word.sources.map((s) => <Badge key={s.id} variant="outline">{s.title}</Badge>)}</div></Field>}
        </CardContent>
      </Card>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
      {children}
    </div>
  );
}
