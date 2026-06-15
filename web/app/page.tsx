"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { GraduationCap, Sparkles, Brain, TrendingUp } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { Card } from "@/components/ui/card";

export default function LandingPage() {
  const { user, loading, login, register } = useAuth();
  const router = useRouter();
  const { toast } = useToast();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!loading && user) router.replace("/dashboard");
  }, [user, loading, router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, password, name);
      router.replace("/dashboard");
    } catch (err: any) {
      toast({ title: "Authentication failed", description: err.message, variant: "error" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* Left brand panel */}
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

      {/* Right auth form */}
      <div className="flex items-center justify-center p-6">
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
          <form onSubmit={submit} className="space-y-4">
            {mode === "register" && (
              <div className="space-y-1.5">
                <Label htmlFor="name">Name</Label>
                <Input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" />
              </div>
            )}
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" required minLength={6} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
            </div>
            <Button type="submit" className="w-full" disabled={busy}>
              {busy ? "Please wait…" : mode === "login" ? "Log in" : "Create account"}
            </Button>
          </form>
          <p className="mt-6 text-center text-sm text-muted-foreground">
            {mode === "login" ? "No account yet?" : "Already have an account?"}{" "}
            <button
              className="font-medium text-foreground underline-offset-4 hover:underline"
              onClick={() => setMode(mode === "login" ? "register" : "login")}
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
