"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { CheckCircle2, XCircle, RotateCcw } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface Question { id: string; prompt: string; options: string[]; correct: string; word: string; }

const MODES = [
  { key: "meaning", label: "Meaning" },
  { key: "fill_blank", label: "Fill blank" },
  { key: "collocation", label: "Collocation" },
];

export default function QuizPage() {
  const [mode, setMode] = useState("meaning");
  const [questions, setQuestions] = useState<Question[]>([]);
  const [idx, setIdx] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [score, setScore] = useState(0);
  const [started, setStarted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  async function start(m: string) {
    setLoading(true);
    setMessage("");
    const res = await api<{ questions: Question[]; message?: string }>("/study/quiz", { query: { mode: m, count: 10 } });
    setLoading(false);
    if (!res.questions.length) { setMessage(res.message || "Not enough data to build a quiz."); setStarted(false); return; }
    setQuestions(res.questions);
    setIdx(0); setSelected(null); setScore(0); setStarted(true);
  }

  function choose(opt: string) {
    if (selected) return;
    setSelected(opt);
    if (opt === questions[idx].correct) setScore((s) => s + 1);
  }
  function next() { setSelected(null); setIdx((i) => i + 1); }

  const current = questions[idx];
  const finished = started && idx >= questions.length;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <Card>
        <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
          <Tabs value={mode} onValueChange={setMode}>
            <TabsList>{MODES.map((m) => <TabsTrigger key={m.key} value={m.key}>{m.label}</TabsTrigger>)}</TabsList>
          </Tabs>
          <Button onClick={() => start(mode)} disabled={loading}>{loading ? "Loading…" : "New quiz"}</Button>
        </CardContent>
      </Card>

      {message && <Card><CardContent className="p-6 text-center text-muted-foreground">{message}</CardContent></Card>}

      {!started && !message && (
        <Card><CardContent className="p-10 text-center text-muted-foreground">Choose a mode and start a quiz. Questions are generated from your enriched vocabulary.</CardContent></Card>
      )}

      {started && !finished && current && (
        <motion.div key={current.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
          <Card>
            <CardContent className="space-y-5 p-6">
              <div className="flex items-center justify-between text-sm text-muted-foreground">
                <span>Question {idx + 1} / {questions.length}</span>
                <span>Score {score}</span>
              </div>
              <p className="text-xl font-semibold">{current.prompt}</p>
              <div className="grid gap-2">
                {current.options.map((opt) => {
                  const isCorrect = opt === current.correct;
                  const isChosen = opt === selected;
                  return (
                    <button
                      key={opt}
                      onClick={() => choose(opt)}
                      disabled={!!selected}
                      className={cn(
                        "flex items-center justify-between rounded-md border p-3 text-left text-sm transition-colors",
                        !selected && "hover:bg-secondary",
                        selected && isCorrect && "border-success bg-success/10",
                        selected && isChosen && !isCorrect && "border-destructive bg-destructive/10",
                      )}
                    >
                      <span>{opt}</span>
                      {selected && isCorrect && <CheckCircle2 className="h-5 w-5 text-success" />}
                      {selected && isChosen && !isCorrect && <XCircle className="h-5 w-5 text-destructive" />}
                    </button>
                  );
                })}
              </div>
              {selected && <Button onClick={next} className="w-full">{idx + 1 >= questions.length ? "See results" : "Next question"}</Button>}
            </CardContent>
          </Card>
        </motion.div>
      )}

      {finished && (
        <Card>
          <CardContent className="flex flex-col items-center gap-4 p-10 text-center">
            <p className="text-4xl font-bold">{score} / {questions.length}</p>
            <p className="text-muted-foreground">{Math.round((score / questions.length) * 100)}% correct</p>
            <Button onClick={() => start(mode)} className="gap-2"><RotateCcw className="h-4 w-4" /> Try again</Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
