"use client";

import { useEffect, useRef, useState } from "react";
import { UploadCloud, Link2, FileText, RefreshCw, Trash2, Loader2, CheckCircle2, AlertCircle, Download, Eye } from "lucide-react";
import { api, BASE_URL, getToken } from "@/lib/api";
import { useApiData } from "@/hooks/useApiData";
import type { Source, Job } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Textarea, Label } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";

export default function ImportPage() {
  const { toast } = useToast();
  const { data, loading, reload } = useApiData<{ items: Source[] }>("/sources");
  const [busy, setBusy] = useState(false);
  const [text, setText] = useState("");
  const [textTitle, setTextTitle] = useState("");
  const [url, setUrl] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const [activeJob, setActiveJob] = useState<string | null>(null);
  const [previewId, setPreviewId] = useState<string | null>(null);

  async function download(id: string) {
    try {
      const res = await api<{ url: string }>(`/sources/${id}/download-url`);
      window.open(res.url, "_blank");
    } catch (e: any) {
      toast({ title: "Download unavailable", description: e.message, variant: "error" });
    }
  }

  // Poll while any source is processing.
  useEffect(() => {
    const processing = (data?.items || []).some((s) => ["pending", "processing"].includes(s.status));
    if (!processing) return;
    const t = setInterval(reload, 2500);
    return () => clearInterval(t);
  }, [data, reload]);

  async function submitText() {
    if (text.trim().length < 10) return toast({ title: "Add more text", variant: "error" });
    setBusy(true);
    try {
      await api("/sources/text", { method: "POST", body: { title: textTitle || "Pasted text", text } });
      setText(""); setTextTitle("");
      toast({ title: "Processing started", variant: "success" });
      reload();
    } catch (e: any) {
      toast({ title: "Failed", description: e.message, variant: "error" });
    } finally { setBusy(false); }
  }

  async function submitUrl() {
    if (!url.startsWith("http")) return toast({ title: "Enter a valid URL", variant: "error" });
    setBusy(true);
    try {
      await api("/sources/url", { method: "POST", body: { url } });
      setUrl("");
      toast({ title: "Fetching & processing", variant: "success" });
      reload();
    } catch (e: any) {
      toast({ title: "Failed", description: e.message, variant: "error" });
    } finally { setBusy(false); }
  }

  async function submitFile(file: File) {
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`${BASE_URL}/sources/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${getToken()}` },
        body: fd,
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "Upload failed");
      toast({ title: "Uploaded & processing", variant: "success" });
      reload();
    } catch (e: any) {
      toast({ title: "Failed", description: e.message, variant: "error" });
    } finally { setBusy(false); if (fileRef.current) fileRef.current.value = ""; }
  }

  async function reprocess(id: string) {
    await api(`/sources/${id}/reprocess`, { method: "POST" });
    toast({ title: "Reprocessing", variant: "success" });
    reload();
  }
  async function remove(id: string) {
    await api(`/sources/${id}`, { method: "DELETE" });
    toast({ title: "Deleted" });
    reload();
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader><CardTitle>Add a source</CardTitle></CardHeader>
        <CardContent>
          <Tabs defaultValue="file">
            <TabsList>
              <TabsTrigger value="file">File</TabsTrigger>
              <TabsTrigger value="text">Text</TabsTrigger>
              <TabsTrigger value="url">URL</TabsTrigger>
            </TabsList>

            <TabsContent value="file">
              <div
                className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed py-12 text-center transition-colors hover:border-primary"
                onClick={() => fileRef.current?.click()}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => { e.preventDefault(); if (e.dataTransfer.files[0]) submitFile(e.dataTransfer.files[0]); }}
              >
                <UploadCloud className="h-10 w-10 text-muted-foreground" />
                <p className="font-medium">Drop a file or click to browse</p>
                <p className="text-sm text-muted-foreground">PDF, DOCX, TXT, CSV, JSON</p>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".pdf,.docx,.txt,.csv,.json"
                  className="hidden"
                  onChange={(e) => e.target.files?.[0] && submitFile(e.target.files[0])}
                />
              </div>
            </TabsContent>

            <TabsContent value="text">
              <div className="space-y-3">
                <div className="space-y-1.5">
                  <Label>Title</Label>
                  <Input value={textTitle} onChange={(e) => setTextTitle(e.target.value)} placeholder="e.g. Reading passage – Climate" />
                </div>
                <div className="space-y-1.5">
                  <Label>Paste text</Label>
                  <Textarea rows={8} value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste a reading passage, transcript or essay…" />
                </div>
                <Button onClick={submitText} disabled={busy} className="w-full">Process text</Button>
              </div>
            </TabsContent>

            <TabsContent value="url">
              <div className="space-y-3">
                <div className="space-y-1.5">
                  <Label>Web page URL</Label>
                  <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" />
                </div>
                <Button onClick={submitUrl} disabled={busy} className="w-full gap-2"><Link2 className="h-4 w-4" /> Fetch & process</Button>
              </div>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Your sources</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {loading && <p className="text-sm text-muted-foreground">Loading…</p>}
          {!loading && !data?.items.length && <p className="text-sm text-muted-foreground">No sources yet.</p>}
          {data?.items.map((s) => (
            <div key={s.id} className="flex items-center gap-3 rounded-lg border p-3">
              <FileText className="h-5 w-5 shrink-0 text-muted-foreground" />
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{s.title}</p>
                <p className="truncate text-xs text-muted-foreground">
                  {(s.originalFileName || s.type).toString()} · {s.type.toUpperCase()} · {s.stats?.wordsExtracted ?? 0} words
                </p>
              </div>
              <StatusBadge status={s.status} />
              <Button variant="ghost" size="icon" onClick={() => setPreviewId(s.id)} title="Preview text"><Eye className="h-4 w-4" /></Button>
              {s.s3Key && (
                <Button variant="ghost" size="icon" onClick={() => download(s.id)} title="Download original"><Download className="h-4 w-4" /></Button>
              )}
              <Button variant="ghost" size="icon" onClick={() => setActiveJob(s.id)} title="Logs"><FileText className="h-4 w-4" /></Button>
              <Button variant="ghost" size="icon" onClick={() => reprocess(s.id)} title="Reprocess"><RefreshCw className="h-4 w-4" /></Button>
              <Button variant="ghost" size="icon" onClick={() => remove(s.id)} title="Delete"><Trash2 className="h-4 w-4 text-destructive" /></Button>
            </div>
          ))}
        </CardContent>
      </Card>

      <JobLogsDialog sourceId={activeJob} onClose={() => setActiveJob(null)} />
      <SourcePreviewDialog sourceId={previewId} onClose={() => setPreviewId(null)} />
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  if (status === "done") return <Badge variant="success" className="gap-1"><CheckCircle2 className="h-3 w-3" /> Done</Badge>;
  if (status === "error") return <Badge variant="secondary" className="gap-1 bg-destructive/15 text-destructive"><AlertCircle className="h-3 w-3" /> Error</Badge>;
  return <Badge variant="accent" className="gap-1"><Loader2 className="h-3 w-3 animate-spin" /> {status}</Badge>;
}

function JobLogsDialog({ sourceId, onClose }: { sourceId: string | null; onClose: () => void }) {
  const [job, setJob] = useState<Job | null>(null);
  useEffect(() => {
    if (!sourceId) return;
    let active = true;
    async function load() {
      const res = await api<{ items: Job[] }>("/jobs", { query: { limit: 25 } });
      const match = res.items.find((j: any) => (j as any).sourceId === sourceId) || res.items[0];
      if (active) setJob(match || null);
    }
    load();
    const t = setInterval(load, 2500);
    return () => { active = false; clearInterval(t); };
  }, [sourceId]);

  return (
    <Dialog open={!!sourceId} onOpenChange={(v) => !v && onClose()}>
      <DialogHeader><DialogTitle>Extraction logs</DialogTitle></DialogHeader>
      <div className="max-h-80 space-y-1 overflow-y-auto rounded-md bg-secondary/50 p-3 font-mono text-xs">
        {job?.logs?.length ? (
          job.logs.map((l, i) => <div key={i}>· {l.msg}</div>)
        ) : (
          <p className="text-muted-foreground">No logs yet…</p>
        )}
        {job?.error && <div className="text-destructive">ERROR: {job.error}</div>}
      </div>
    </Dialog>
  );
}

function SourcePreviewDialog({ sourceId, onClose }: { sourceId: string | null; onClose: () => void }) {
  const { data: source, loading } = useApiData<Source>(sourceId ? `/sources/${sourceId}` : null);
  return (
    <Dialog open={!!sourceId} onOpenChange={(v) => !v && onClose()}>
      <DialogHeader><DialogTitle>{source?.title || "Source text"}</DialogTitle></DialogHeader>
      {loading || !source ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2 text-xs">
            <Badge variant="secondary">{source.type.toUpperCase()}</Badge>
            {source.originalFileName && <Badge variant="outline">{source.originalFileName}</Badge>}
            <Badge variant="outline">{(source.charCount ?? 0).toLocaleString()} chars</Badge>
            {source.chunkCount != null && <Badge variant="outline">{source.chunkCount} chunks</Badge>}
            {source.storage && <Badge variant="outline">stored: {source.storage}</Badge>}
          </div>
          <div className="max-h-80 overflow-y-auto whitespace-pre-wrap rounded-md bg-secondary/50 p-3 text-sm leading-relaxed">
            {(source.rawText || "").trim() || <span className="text-muted-foreground">No extracted text yet.</span>}
          </div>
          <p className="text-xs text-muted-foreground">Text is stored in MongoDB; the original file is stored in S3.</p>
        </div>
      )}
    </Dialog>
  );
}
