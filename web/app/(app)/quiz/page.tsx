"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { CheckCircle2, XCircle, RotateCcw } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { WorkStatus, workError } from "@/components/ui/work-status";
import { useHideOrientation } from "@/components/orientation-visibility";
import { usePwaInstallContext } from "@/components/pwa-install-provider";

interface Question { id: string; prompt: string; options: string[]; correct: string; word: string; }
interface QuizAnswer { questionId: string; choice: string; }
interface SavedQuiz {
  mode: string | null;
  questions: Question[];
  index: number;
  answers: QuizAnswer[];
  score: number;
}

const MODES = [
  { key: "meaning", label: "Meaning" },
  { key: "fill_blank", label: "Fill blank" },
  { key: "collocation", label: "Collocation" },
];

export default function QuizPage() {
  const { canShow: showPwaBanner } = usePwaInstallContext();
  const [mode, setMode] = useState("meaning");
  const [questions, setQuestions] = useState<Question[]>([]);
  const [idx, setIdx] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [score, setScore] = useState(0);
  const [answers, setAnswers] = useState<QuizAnswer[]>([]);
  const [started, setStarted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [restoring, setRestoring] = useState(true);
  const [notice, setNotice] = useState<{ phase: "progress" | "success" | "error"; title: string; detail?: string } | null>(null);
  const ignoreResume = useRef(false);

  useEffect(() => {
    let cancelled = false;
    api<SavedQuiz>("/study/quiz/session")
      .then((saved) => {
        if (cancelled || ignoreResume.current || !saved?.questions?.length) return;
        if (saved.index >= saved.questions.length) return;
        const open = saved.questions[saved.index];
        const prior = (saved.answers || []).find((answer) => answer.questionId === open?.id);
        setMode(saved.mode || "meaning");
        setQuestions(saved.questions);
        setAnswers(saved.answers || []);
        setIdx(saved.index || 0);
        setScore(saved.score || 0);
        setSelected(prior?.choice ?? null);
        setStarted(true);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setRestoring(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function remember(index: number, nextAnswers: QuizAnswer[]) {
    void api("/study/quiz/session", {
      method: "PUT",
      body: { index, answers: nextAnswers },
    }).catch(() => {});
  }

  async function start(m: string) {
    ignoreResume.current = true;
    setLoading(true);
    setNotice({ phase: "progress", title: "Building your quiz" });
    try {
      const res = await api<{ questions: Question[]; message?: string }>("/study/quiz", { query: { mode: m, count: 10 } });
      if (!res.questions.length) {
        setNotice({ phase: "error", title: "No quiz yet", detail: res.message || "Not enough vocabulary to build a quiz." });
        setStarted(false);
        return;
      }
      await api("/study/quiz/session", { method: "POST", body: { mode: m, questions: res.questions } });
      setQuestions(res.questions);
      setAnswers([]);
      setIdx(0); setSelected(null); setScore(0); setStarted(true);
      setNotice(null);
    } catch (err) {
      setNotice({ phase: "error", title: "Could not start the quiz", detail: workError(err) });
      setStarted(false);
    } finally {
      setLoading(false);
    }
  }

  function choose(opt: string) {
    if (selected || !questions[idx]) return;
    const question = questions[idx];
    const nextAnswers = answers.filter((answer) => answer.questionId !== question.id);
    nextAnswers.push({ questionId: question.id, choice: opt });
    const nextScore = questions.reduce((total, item) => (
      total + (nextAnswers.some((answer) => answer.questionId === item.id && answer.choice === item.correct) ? 1 : 0)
    ), 0);
    setSelected(opt);
    setAnswers(nextAnswers);
    setScore(nextScore);
    remember(idx, nextAnswers);
  }
  function next() {
    const following = idx + 1;
    setSelected(null);
    if (following >= questions.length) {
      setIdx(following);
      void api("/study/quiz/session", { method: "DELETE" }).catch(() => {});
      return;
    }
    setIdx(following);
    remember(following, answers);
  }

  const current = questions[idx];
  const finished = started && idx >= questions.length;
  const answering = started && !finished && Boolean(current);
  useHideOrientation(restoring || answering);

  if (restoring) {
    return <div className="flex h-64 items-center justify-center text-muted-foreground">Loading quiz…</div>;
  }

  return (
    <div className="page-stack">
      {!answering && (
        <Card data-quiz-setup>
          <CardContent className="flex flex-col gap-3 p-4">
            <Tabs value={mode} onValueChange={setMode} className="w-full">
              <TabsList>{MODES.map((m) => <TabsTrigger key={m.key} value={m.key}>{m.label}</TabsTrigger>)}</TabsList>
            </Tabs>
            <Button className="w-full sm:w-auto sm:self-end" onClick={() => start(mode)} disabled={loading}>{loading ? "Building…" : "New quiz"}</Button>
            {notice && <WorkStatus phase={notice.phase} title={notice.title} detail={notice.detail} onDismiss={() => setNotice(null)} />}
          </CardContent>
        </Card>
      )}

      {!started && !notice && (
        <Card><CardContent className="p-4 text-center text-sm text-muted-foreground">Choose a mode and start a quiz. Questions are generated from your enriched vocabulary.</CardContent></Card>
      )}

      {answering && current && (
        <div
          data-quiz-question
          className={cn(
            "max-lg:fixed max-lg:inset-x-0 max-lg:z-20 max-lg:flex max-lg:flex-col max-lg:bg-background max-lg:px-page max-lg:pb-3 max-lg:pt-3",
            "max-lg:top-[var(--app-topbar-height)]",
            showPwaBanner
              ? "max-lg:bottom-[calc(var(--content-bottom-offset)+7.5rem)]"
              : "max-lg:bottom-[var(--content-bottom-offset)]",
          )}
        >
          <motion.div
            key={current.id}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex min-h-0 flex-1 flex-col"
          >
            <Card className="flex min-h-0 flex-1 flex-col">
              <CardContent className="flex min-h-0 flex-1 flex-col gap-4 p-4">
                <div className="flex items-center justify-between text-sm text-muted-foreground">
                  <span>Question {idx + 1} / {questions.length}</span>
                  <span>Score {score}</span>
                </div>
                <p className="text-base font-semibold">{current.prompt}</p>
                <div className="grid min-h-0 flex-1 content-start gap-2 overflow-y-auto">
                  {current.options.map((opt) => {
                    const isCorrect = opt === current.correct;
                    const isChosen = opt === selected;
                    return (
                      <button
                        key={opt}
                        onClick={() => choose(opt)}
                        disabled={!!selected}
                        className={cn(
                          "flex items-center justify-between gap-3 rounded-lg border p-3 text-left text-sm transition-colors",
                          !selected && "hover:bg-secondary",
                          selected && isCorrect && "border-success bg-success/10",
                          selected && isChosen && !isCorrect && "border-destructive bg-destructive/10",
                        )}
                      >
                        <span>{opt}</span>
                        {selected && isCorrect && <CheckCircle2 className="h-5 w-5 shrink-0 text-success" />}
                        {selected && isChosen && !isCorrect && <XCircle className="h-5 w-5 shrink-0 text-destructive" />}
                      </button>
                    );
                  })}
                </div>
                {selected && (
                  <Button data-quiz-next onClick={next} className="w-full shrink-0">
                    {idx + 1 >= questions.length ? "See results" : "Next question"}
                  </Button>
                )}
              </CardContent>
            </Card>
          </motion.div>
        </div>
      )}

      {finished && (
        <Card>
          <CardContent className="flex flex-col items-center gap-4 p-4 text-center">
            <p className="text-2xl font-semibold tabular-nums">{score} / {questions.length}</p>
            <p className="text-muted-foreground">{Math.round((score / questions.length) * 100)}% correct</p>
            <Button onClick={() => start(mode)} className="gap-2"><RotateCcw className="h-4 w-4" /> Try again</Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
