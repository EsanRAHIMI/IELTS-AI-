"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { GraduationCap, Sparkles, Brain, TrendingUp, Loader2 } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { getAuthFormFeedback, validateAuthForm, type AuthField, type AuthFormFeedback } from "@/lib/auth-errors";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Alert, FieldError } from "@/components/ui/alert";
import { cn } from "@/lib/utils";

export default function LandingPage() {
  const { user, loading, login, register } = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<AuthFormFeedback | null>(null);

  useEffect(() => {
    if (!loading && user) router.replace("/dashboard");
  }, [user, loading, router]);

  function clearFieldError(field: AuthField) {
    setFeedback((prev) => {
      if (!prev?.fieldErrors[field]) return prev;
      const fieldErrors = { ...prev.fieldErrors };
      delete fieldErrors[field];
      return { ...prev, fieldErrors };
    });
  }

  function switchMode(next: "login" | "register") {
    setMode(next);
    setFeedback(null);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setFeedback(null);

    const clientError = validateAuthForm(mode, { email, password, name });
    if (clientError) {
      setFeedback(clientError);
      return;
    }

    setBusy(true);
    try {
      if (mode === "login") await login(email.trim(), password);
      else await register(email.trim(), password, name.trim());
      router.replace("/dashboard");
    } catch (err) {
      setFeedback(getAuthFormFeedback(err, mode));
    } finally {
      setBusy(false);
    }
  }

  const fieldError = (field: AuthField) => feedback?.fieldErrors[field];

  return (
    <div className="grid min-h-app lg:grid-cols-2">
      <div className="relative hidden flex-col justify-between bg-primary p-12 text-primary-foreground lg:flex">
        <div className="flex items-center gap-2 text-lg font-semibold">
          <GraduationCap className="h-6 w-6 text-accent" />
          IELTS AI Mastery Engine
        </div>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="space-y-6"
        >
          <h1 className="text-4xl font-bold leading-tight">
            Turn any source into a ranked IELTS study system.
          </h1>
          <p className="max-w-md text-primary-foreground/70">
            Import readings, transcripts, essays and articles. The engine extracts the highest-value
            vocabulary, collocations and sentence patterns, then trains you with spaced repetition.
          </p>
          <div className="grid grid-cols-1 gap-4 pt-4">
            <Feature icon={<Sparkles className="h-5 w-5" />} text="AI meaning, Persian translation & examples" />
            <Feature icon={<Brain className="h-5 w-5" />} text="SM-2 spaced repetition flashcards & quizzes" />
            <Feature icon={<TrendingUp className="h-5 w-5" />} text="Priority ranking & progress tracking" />
          </div>
        </motion.div>
        <p className="text-sm text-primary-foreground/50">Built for band 7.5+ preparation · 2026 standards</p>
      </div>

      <div className="flex items-center justify-center p-6 pt-safe px-safe pb-safe-or-4">
        <Card className="w-full max-w-md p-8">
          <div className="mb-6 text-center lg:hidden">
            <div className="mb-2 flex items-center justify-center gap-2 text-lg font-semibold">
              <GraduationCap className="h-6 w-6 text-accent" /> IELTS AI Mastery
            </div>
          </div>
          <h2 className="text-2xl font-bold">{mode === "login" ? "Welcome back" : "Create your account"}</h2>
          <p className="mb-6 text-sm text-muted-foreground">
            {mode === "login" ? "Log in to continue your preparation." : "Start building your personal IELTS corpus."}
          </p>

          <AnimatePresence mode="wait">
            {feedback && (
              <motion.div
                key={feedback.title + feedback.message}
                initial={{ opacity: 0, y: -8, height: 0 }}
                animate={{ opacity: 1, y: 0, height: "auto" }}
                exit={{ opacity: 0, y: -4, height: 0 }}
                transition={{ duration: 0.25 }}
                className="mb-4 overflow-hidden"
              >
                <Alert
                  variant="error"
                  title={feedback.title}
                  hint={feedback.hint}
                  onDismiss={() => setFeedback(null)}
                >
                  {feedback.message}
                </Alert>
              </motion.div>
            )}
          </AnimatePresence>

          <form onSubmit={submit} className="space-y-4" noValidate>
            {mode === "register" && (
              <div className="space-y-1.5">
                <Label htmlFor="name">Name</Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => {
                    setName(e.target.value);
                    clearFieldError("name");
                  }}
                  placeholder="Your name"
                  aria-invalid={Boolean(fieldError("name"))}
                  aria-describedby={fieldError("name") ? "name-error" : undefined}
                  className={cn(fieldError("name") && "border-destructive focus-visible:ring-destructive")}
                />
                <FieldError id="name-error" message={fieldError("name")} />
              </div>
            )}
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  clearFieldError("email");
                }}
                placeholder="you@example.com"
                aria-invalid={Boolean(fieldError("email"))}
                aria-describedby={fieldError("email") ? "email-error" : undefined}
                className={cn(fieldError("email") && "border-destructive focus-visible:ring-destructive")}
              />
              <FieldError id="email-error" message={fieldError("email")} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  clearFieldError("password");
                }}
                placeholder="••••••••"
                aria-invalid={Boolean(fieldError("password"))}
                aria-describedby={fieldError("password") ? "password-error" : undefined}
                className={cn(fieldError("password") && "border-destructive focus-visible:ring-destructive")}
              />
              <FieldError id="password-error" message={fieldError("password")} />
              {mode === "register" && !fieldError("password") && (
                <p className="text-xs text-muted-foreground">At least 6 characters.</p>
              )}
            </div>
            <Button type="submit" className="w-full gap-2" disabled={busy}>
              {busy && <Loader2 className="h-4 w-4 animate-spin" />}
              {busy ? "Please wait…" : mode === "login" ? "Log in" : "Create account"}
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-muted-foreground">
            {mode === "login" ? "No account yet?" : "Already have an account?"}{" "}
            <button
              type="button"
              className="font-medium text-foreground underline-offset-4 hover:underline"
              onClick={() => switchMode(mode === "login" ? "register" : "login")}
            >
              {mode === "login" ? "Register" : "Log in"}
            </button>
          </p>
        </Card>
      </div>
    </div>
  );
}

function Feature({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-foreground/10 text-accent">{icon}</div>
      <span className="text-sm text-primary-foreground/90">{text}</span>
    </div>
  );
}
