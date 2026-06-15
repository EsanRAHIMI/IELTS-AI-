"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { RotateCcw, Keyboard, PartyPopper } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Card as CardType } from "@/types";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";

const GRADES = [
  { key: "again", label: "Again", hint: "1", cls: "bg-destructive text-destructive-foreground hover:bg-destructive/90" },
  { key: "hard", label: "Hard", hint: "2", cls: "bg-secondary text-secondary-foreground hover:bg-secondary/80" },
  { key: "good", label: "Good", hint: "3", cls: "bg-primary text-primary-foreground hover:bg-primary/90" },
  { key: "easy", label: "Easy", hint: "4", cls: "bg-success text-success-foreground hover:bg-success/90" },
];

export default function StudyPage() {
  const [queue, setQueue] = useState<CardType[]>([]);
  const [idx, setIdx] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [reviewed, setReviewed] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    const res = await api<{ items: CardType[]; totalDue: number }>("/study/queue", { query: { limit: 40 } });
    setQueue(res.items);
    setIdx(0);
    setRevealed(false);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const current = queue[idx];
  const done = !loading && (!current || idx >= queue.length);

  const grade = useCallback(
    async (g: string) => {
      if (!current) return;
      api(`/study/cards/${current.id}/review`, { method: "POST", body: { grade: g } }).catch(() => {});
      setReviewed((r) => r + 1);
      setRevealed(false);
      setIdx((i) => i + 1);
    },
    [current],
  );

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (done || loading) return;
      if (e.code === "Space" || e.key === "Enter") { e.preventDefault(); if (!revealed) setRevealed(true); return; }
      if (revealed) {
        const map: Record<string, string> = { "1": "again", "2": "hard", "3": "good", "4": "easy" };
        if (map[e.key]) grade(map[e.key]);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [revealed, grade, done, loading]);

  const progress = queue.length ? (idx / queue.length) * 100 : 0;

  if (loading) return <div className="flex h-64 items-center justify-center text-muted-foreground">Loading queue…</div>;

  if (done) {
    return (
      <div className="mx-auto flex max-w-md flex-col items-center gap-4 py-16 text-center">
        <PartyPopper className="h-14 w-14 text-accent" />
        <h2 className="text-2xl font-bold">{reviewed ? "Session complete!" : "Nothing due right now"}</h2>
        <p className="text-muted-foreground">
          {reviewed ? `You reviewed ${reviewed} card${reviewed === 1 ? "" : "s"}. Great work.` : "Add items to study from the Vocabulary, Phrases or Patterns pages, or check back later."}
        </p>
        <div className="flex gap-3">
          <Button onClick={load} className="gap-2"><RotateCcw className="h-4 w-4" /> Reload queue</Button>
          <Link href="/vocabulary"><Button variant="outline">Add cards</Button></Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>Card {idx + 1} of {queue.length}</span>
          <span className="flex items-center gap-1"><Keyboard className="h-4 w-4" /> Space reveal · 1–4 grade</span>
        </div>
        <Progress value={progress} />
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={current.id}
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -16 }}
          transition={{ duration: 0.2 }}
        >
          <Card className="min-h-[320px]">
            <CardContent className="flex min-h-[320px] flex-col items-center justify-center gap-4 p-8 text-center">
              <Badge variant="secondary">{current.type.replace("_", " ")}</Badge>
              <p className="text-3xl font-bold">{current.front}</p>

              {revealed ? (
                <div className="w-full space-y-3 border-t pt-4 text-left">
                  {current.back.persianMeaning && <p className="farsi text-lg">{current.back.persianMeaning}</p>}
                  {current.back.simpleEnglishMeaning && <p className="text-muted-foreground">{current.back.simpleEnglishMeaning}</p>}
                  {!!current.back.collocations?.length && (
                    <div className="flex flex-wrap gap-1.5">{current.back.collocations.map((c) => <Badge key={c} variant="secondary">{c}</Badge>)}</div>
                  )}
                  {!!current.back.examples?.length && (
                    <ul className="space-y-1.5">{current.back.examples.filter(Boolean).map((e, i) => <li key={i} className="rounded-md bg-secondary/50 p-2 text-sm">{e}</li>)}</ul>
                  )}
                  {current.back.notes && <p className="text-sm text-muted-foreground">{current.back.notes}</p>}
                </div>
              ) : (
                <Button variant="outline" onClick={() => setRevealed(true)}>Reveal answer (Space)</Button>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </AnimatePresence>

      {revealed && (
        <div className="grid grid-cols-4 gap-2">
          {GRADES.map((g) => (
            <button key={g.key} onClick={() => grade(g.key)} className={`flex flex-col items-center rounded-md px-3 py-3 text-sm font-medium transition-colors ${g.cls}`}>
              {g.label}<span className="text-xs opacity-70">{g.hint}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
