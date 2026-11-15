"use client";

import { useCallback, useEffect, useRef, useState, type PointerEvent } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { AlertCircle, ArrowLeft, ArrowRight, CheckCircle2, Languages, RotateCcw, Keyboard, PartyPopper } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useSpeech } from "@/lib/speech";
import { cn } from "@/lib/utils";
import type { Card as CardType, CardTranslation } from "@/types";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { workError } from "@/components/ui/work-status";

const RTL = new Set(["fa", "ar", "ur"]);

function savedTranslation(card: CardType, language: string): CardTranslation | null {
  const saved = card.translations?.[language];
  if (!saved) return null;
  const pieces = [saved.front, saved.meaning, saved.notes, ...(saved.examples || []), ...(saved.collocations || [])];
  return pieces.some((part) => (part || "").trim()) ? saved : null;
}

const GRADES = [
  { key: "again", label: "Again", hint: "1", cls: "bg-destructive text-destructive-foreground hover:bg-destructive/90" },
  { key: "hard", label: "Hard", hint: "2", cls: "bg-secondary text-secondary-foreground hover:bg-secondary/80" },
  { key: "good", label: "Good", hint: "3", cls: "bg-primary text-primary-foreground hover:bg-primary/90" },
  { key: "easy", label: "Easy", hint: "4", cls: "bg-success text-success-foreground hover:bg-success/90" },
];

const GRADE_BY_CODE: Record<string, string> = {
  Digit1: "again", Numpad1: "again",
  Digit2: "hard", Numpad2: "hard",
  Digit3: "good", Numpad3: "good",
  Digit4: "easy", Numpad4: "easy",
};

const GRADE_BY_KEY: Record<string, string> = {
  "1": "again", "2": "hard", "3": "good", "4": "easy",
  "۱": "again", "۲": "hard", "۳": "good", "۴": "easy",
  "١": "again", "٢": "hard", "٣": "good", "٤": "easy",
};

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
}

function gradeFromEvent(e: KeyboardEvent): string | null {
  return GRADE_BY_CODE[e.code] || GRADE_BY_KEY[e.key] || null;
}

export default function StudyPage() {
  const { user } = useAuth();
  const language = user?.settings.translationLanguage || "fa";
  const [queue, setQueue] = useState<CardType[]>([]);
  const [idx, setIdx] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [reviewed, setReviewed] = useState(0);
  const [reached, setReached] = useState(0);
  const [grades, setGrades] = useState<Record<string, string>>({});
  const { enabled: speakOn, ready: speakReady, speak, stop } = useSpeech();
  const [toast, setToast] = useState<{ text: string; tone: "success" | "error" } | null>(null);
  const [translating, setTranslating] = useState(false);
  const [translateError, setTranslateError] = useState("");
  const toastTimer = useRef<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const res = await api<{ items: CardType[]; totalDue: number; reviewedToday?: number }>("/study/queue", { query: { limit: 40 } });
    setQueue(res.items);
    setIdx(0);
    setReached(0);
    setGrades({});
    setRevealed(false);
    setReviewed(res.reviewedToday || 0);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const current = queue[idx];

  useEffect(() => {
    if (!speakReady) return;
    if (!speakOn || !current?.front) {
      stop();
      return;
    }
    speak(current.front);
    return () => stop();
  }, [speakReady, speakOn, current?.id, current?.front, speak, stop]);
  const done = !loading && (!current || idx >= queue.length);
  const translation = current ? savedTranslation(current, language) : null;
  const canGoBack = idx > 0;
  const canGoForward = idx < reached;
  const chosenGrade = current ? grades[current.id] : undefined;
  const grading = useRef(false);

  const flash = useCallback((text: string, tone: "success" | "error") => {
    setToast({ text, tone });
    if (toastTimer.current) window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(null), 2800);
  }, []);

  useEffect(() => () => {
    if (toastTimer.current) window.clearTimeout(toastTimer.current);
  }, []);

  const translateCard = useCallback(async () => {
    if (!current || savedTranslation(current, language) || translating) return;
    setTranslating(true);
    setTranslateError("");
    try {
      const saved = await api<CardTranslation>(`/study/cards/${current.id}/translate`, { method: "POST" });
      setQueue((items) => items.map((card) => (
        card.id === current.id
          ? { ...card, translations: { ...(card.translations || {}), [saved.language || language]: saved } }
          : card
      )));
    } catch (err) {
      setTranslateError(err instanceof Error ? err.message : "Translation failed");
    } finally {
      setTranslating(false);
    }
  }, [current, language, translating]);

  const grade = useCallback(
    async (g: string) => {
      if (!current || grading.current) return;
      const prior = grades[current.id];
      if (prior === g) return;
      grading.current = true;
      try {
        await api(`/study/cards/${current.id}/review`, { method: "POST", body: { grade: g } });
      } catch (err) {
        grading.current = false;
        flash(workError(err, "Could not save this review"), "error");
        return;
      }
      setGrades((prev) => ({ ...prev, [current.id]: g }));
      flash("Answer saved", "success");
      if (prior) {
        grading.current = false;
        return;
      }
      setReviewed((r) => r + 1);
      setRevealed(false);
      setIdx((i) => i + 1);
      setReached((r) => Math.max(r, idx + 1));
    },
    [current, flash, grades, idx],
  );

  const goBack = useCallback(() => {
    if (idx <= 0) return;
    grading.current = false;
    setRevealed(false);
    setIdx((i) => i - 1);
  }, [idx]);

  const goForward = useCallback(() => {
    if (idx >= reached) return;
    grading.current = false;
    setRevealed(false);
    setIdx((i) => i + 1);
  }, [idx, reached]);

  useEffect(() => {
    grading.current = false;
  }, [idx]);

  const keys = useRef({
    loading, done, revealed, graded: !!chosenGrade, canGoBack, canGoForward,
    reveal: () => setRevealed(true),
    grade, goBack, goForward,
  });
  keys.current = {
    loading, done, revealed, graded: !!chosenGrade, canGoBack, canGoForward,
    reveal: () => setRevealed(true), grade, goBack, goForward,
  };

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.metaKey || e.ctrlKey || e.altKey || e.isComposing) return;
      if (isTypingTarget(e.target)) return;
      const state = keys.current;
      if (state.loading) return;
      if (e.key === "ArrowLeft") {
        if (!state.canGoBack) return;
        e.preventDefault();
        state.goBack();
        return;
      }
      if (e.key === "ArrowRight") {
        if (!state.canGoForward) return;
        e.preventDefault();
        state.goForward();
        return;
      }
      if (state.done) return;
      if (e.code === "Space" || e.key === "Enter") {
        e.preventDefault();
        if (!state.revealed) state.reveal();
        return;
      }
      if ((!state.revealed && !state.graded) || e.repeat) return;
      const choice = gradeFromEvent(e);
      if (!choice) return;
      e.preventDefault();
      state.grade(choice);
    }
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, []);

  const swipe = useRef<{ x: number; y: number } | null>(null);
  function onPointerDown(e: PointerEvent) {
    if (e.button !== 0) return;
    swipe.current = { x: e.clientX, y: e.clientY };
  }
  function onPointerUp(e: PointerEvent) {
    if (!swipe.current) return;
    const dx = e.clientX - swipe.current.x;
    const dy = e.clientY - swipe.current.y;
    swipe.current = null;
    if (dx > 72 && Math.abs(dx) > Math.abs(dy)) goBack();
    else if (dx < -72 && Math.abs(dx) > Math.abs(dy) && canGoForward) goForward();
  }

  useEffect(() => { setTranslateError(""); }, [idx]);

  const progress = queue.length ? (idx / queue.length) * 100 : 0;

  if (loading) return <div className="flex h-64 items-center justify-center text-muted-foreground">Loading queue…</div>;

  const cornerToast = toast && (
    <div
      role="status"
      className={cn(
        "pointer-events-none fixed right-4 top-[calc(var(--app-topbar-height)+0.75rem)] z-40 flex max-w-[16rem] items-center gap-2 rounded-full border bg-card/95 px-3 py-1.5 text-sm shadow-lg",
        toast.tone === "success" ? "border-success/40" : "border-destructive/40",
      )}
    >
      {toast.tone === "success" ? <CheckCircle2 className="h-4 w-4 shrink-0 text-success" /> : <AlertCircle className="h-4 w-4 shrink-0 text-destructive" />}
      <span className="truncate font-medium">{toast.text}</span>
    </div>
  );

  const backButton = (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      className="shrink-0"
      aria-label="Previous card"
      title="Previous card"
      disabled={!canGoBack}
      onClick={goBack}
    >
      <ArrowLeft className="h-4 w-4" />
    </Button>
  );

  const forwardButton = canGoForward ? (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      className="shrink-0"
      aria-label="Next card"
      title="Next card"
      onClick={goForward}
    >
      <ArrowRight className="h-4 w-4" />
    </Button>
  ) : null;

  if (done) {
    return (
      <div
        className="relative mx-auto max-w-md"
        onPointerDown={onPointerDown}
        onPointerUp={onPointerUp}
        onPointerCancel={() => { swipe.current = null; }}
      >
        {cornerToast}
        {canGoBack && <div className="absolute left-0 top-0">{backButton}</div>}
        {forwardButton && <div className="absolute right-0 top-0">{forwardButton}</div>}
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
      </div>
    );
  }

  return (
    <div
      className="mx-auto max-w-2xl space-y-6"
      onPointerDown={onPointerDown}
      onPointerUp={onPointerUp}
      onPointerCancel={() => { swipe.current = null; }}
    >
      {cornerToast}
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          {backButton}
          <div className="flex min-w-0 flex-1 flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
            <span>Card {idx + 1} of {queue.length}</span>
            <span className="hidden items-center gap-1 sm:flex"><Keyboard className="h-4 w-4" /> Space reveal · 1–4 grade · ← back</span>
          </div>
          {forwardButton}
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
          <Card className="min-h-[280px] sm:min-h-[320px]">
            <CardContent className="flex min-h-[280px] flex-col items-center justify-center gap-4 p-5 text-center sm:min-h-[320px] sm:p-8">
              <Badge variant="secondary">{current.type.replace("_", " ")}</Badge>
              <p className="max-w-full break-words text-2xl font-bold sm:text-3xl">{current.front}</p>

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
                  <div className="space-y-2 border-t pt-3">
                    <Button type="button" variant="outline" size="sm" className="gap-2" onClick={translateCard} disabled={translating || !!translation}>
                      <Languages className="h-4 w-4" />
                      {translating ? "Translating…" : translation ? "Translated" : "Translate"}
                    </Button>
                    {translateError && <p className="text-sm text-destructive">{translateError}</p>}
                    {translation && (
                      <div dir={RTL.has(language) ? "rtl" : "ltr"} className={RTL.has(language) ? "farsi space-y-2" : "space-y-2"}>
                        {translation.front && <p className="font-medium">{translation.front}</p>}
                        {translation.meaning && <p>{translation.meaning}</p>}
                        {!!translation.collocations?.length && (
                          <div className="flex flex-wrap gap-1.5">{translation.collocations.map((c) => <Badge key={c} variant="outline">{c}</Badge>)}</div>
                        )}
                        {!!translation.examples?.length && (
                          <ul className="space-y-1.5">{translation.examples.map((example, i) => <li key={i} className="rounded-md bg-secondary/50 p-2 text-sm">{example}</li>)}</ul>
                        )}
                        {translation.notes && <p className="text-sm text-muted-foreground">{translation.notes}</p>}
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <Button variant="outline" onClick={() => setRevealed(true)}>Reveal answer (Space)</Button>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </AnimatePresence>

      {(revealed || chosenGrade) && (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {GRADES.map((g) => {
            const selected = chosenGrade === g.key;
            const dimmed = !!chosenGrade && !selected;
            return (
              <button
                key={g.key}
                type="button"
                aria-pressed={selected}
                onClick={() => grade(g.key)}
                className={cn(
                  "flex min-h-[3.25rem] flex-col items-center justify-center rounded-xl px-2 py-3 text-sm font-medium transition-colors",
                  g.cls,
                  selected && "ring-2 ring-foreground ring-offset-2 ring-offset-background",
                  dimmed && "opacity-40 saturate-50",
                )}
              >
                {g.label}<span className="text-xs opacity-70">{g.hint}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
