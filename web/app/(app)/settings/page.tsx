"use client";

import { useEffect, useState } from "react";
import { Save } from "lucide-react";
import { api, setToken } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { User } from "@/types";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";

const MODULES = ["Academic", "General", "Writing", "Speaking", "Reading", "Listening"];
const PROVIDERS = ["openai", "anthropic", "ollama"];

export default function SettingsPage() {
  const { user, setUser } = useAuth();
  const { toast } = useToast();
  const [aiProvider, setAiProvider] = useState("openai");
  const [dailyTarget, setDailyTarget] = useState(30);
  const [targetBand, setTargetBand] = useState(7.5);
  const [examDate, setExamDate] = useState("");
  const [focusModules, setFocusModules] = useState<string[]>([]);
  const [health, setHealth] = useState<{ aiConfigured: boolean; aiProvider: string; db: boolean } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (user) {
      const s = user.settings;
      setAiProvider(s.aiProvider);
      setDailyTarget(s.dailyTarget);
      setTargetBand(s.targetBand);
      setExamDate(s.examDate || "");
      setFocusModules(s.focusModules || []);
    }
  }, [user]);

  useEffect(() => {
    api<{ aiConfigured: boolean; aiProvider: string; db: boolean }>("/auth/session").then(setHealth).catch(() => {});
  }, []);

  function toggleModule(m: string) {
    setFocusModules((prev) => (prev.includes(m) ? prev.filter((x) => x !== m) : [...prev, m]));
  }

  async function save() {
    setBusy(true);
    try {
      const updated = await api<User>("/auth/me/settings", {
        method: "PUT",
        body: { aiProvider, dailyTarget: Number(dailyTarget), targetBand: Number(targetBand), examDate: examDate || null, focusModules },
      });
      setUser(updated);
      toast({ title: "Settings saved", variant: "success" });
    } catch (e: any) {
      toast({ title: "Failed", description: e.message, variant: "error" });
    } finally { setBusy(false); }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>AI provider</CardTitle>
          <CardDescription>This choice is used for enrichment when that provider is configured on the server. API keys stay in the backend environment.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label>Preferred provider</Label>
            <Select value={aiProvider} onChange={(e) => setAiProvider(e.target.value)}>
              {PROVIDERS.map((p) => <option key={p} value={p}>{p}</option>)}
            </Select>
          </div>
          {health && (
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="text-muted-foreground">Backend status:</span>
              <Badge variant={health.aiConfigured ? "success" : "muted"}>{health.aiConfigured ? `AI ready (${health.aiProvider})` : "AI key not set"}</Badge>
              <Badge variant={health.db ? "success" : "muted"}>{health.db ? "DB connected" : "DB offline"}</Badge>
            </div>
          )}
          <p className="text-xs text-muted-foreground">API keys are never shown here for security — only their configured status.</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Study goals</CardTitle></CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-3">
          <div className="space-y-1.5">
            <Label>Daily target (cards)</Label>
            <Input type="number" min={5} value={dailyTarget} onChange={(e) => setDailyTarget(Number(e.target.value))} />
          </div>
          <div className="space-y-1.5">
            <Label>Target band</Label>
            <Input type="number" step="0.5" min={4} max={9} value={targetBand} onChange={(e) => setTargetBand(Number(e.target.value))} />
          </div>
          <div className="space-y-1.5">
            <Label>Exam date</Label>
            <Input type="date" value={examDate} onChange={(e) => setExamDate(e.target.value)} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Focus modules</CardTitle><CardDescription>Highlight the areas you want to prioritise.</CardDescription></CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {MODULES.map((m) => {
              const active = focusModules.includes(m);
              return (
                <button
                  key={m}
                  onClick={() => toggleModule(m)}
                  className={`rounded-full border px-4 py-1.5 text-sm transition-colors ${active ? "border-primary bg-primary text-primary-foreground" : "hover:bg-secondary"}`}
                >
                  {m}
                </button>
              );
            })}
          </div>
        </CardContent>
      </Card>

      <PasswordCard />

      <Button onClick={save} disabled={busy} className="gap-2"><Save className="h-4 w-4" /> {busy ? "Saving…" : "Save settings"}</Button>
    </div>
  );
}

function PasswordCard() {
  const { toast } = useToast();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [busy, setBusy] = useState(false);

  async function changePassword() {
    setBusy(true);
    try {
      const res = await api<{ accessToken: string; user: User }>("/auth/change-password", {
        method: "POST",
        body: { currentPassword, newPassword },
      });
      setToken(res.accessToken);
      setCurrentPassword("");
      setNewPassword("");
      toast({ title: "Password updated", variant: "success" });
    } catch (e: any) {
      toast({ title: "Could not change password", description: e.message, variant: "error" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Password</CardTitle>
        <CardDescription>Changing your password signs out other sessions.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label>Current password</Label>
          <Input type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} autoComplete="current-password" />
        </div>
        <div className="space-y-1.5">
          <Label>New password</Label>
          <Input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} autoComplete="new-password" />
        </div>
        <Button type="button" variant="outline" disabled={busy || newPassword.length < 6} onClick={changePassword}>
          {busy ? "Updating…" : "Update password"}
        </Button>
      </CardContent>
    </Card>
  );
}
