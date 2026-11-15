"use client";

import { useEffect, useRef, useState, useMemo, type ReactNode } from "react";
import { UploadCloud, Link2, FileText, RefreshCw, Trash2, Loader2, CheckCircle2, AlertCircle, AlertTriangle, ScanLine, Layers, Download, Eye, Square } from "lucide-react";
import { api, BASE_URL, getToken } from "@/lib/api";
import { useApiData } from "@/hooks/useApiData";
import type { Source, Job, SourceDeleteImpact } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Textarea, Label } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import { WorkStatus, workError, type WorkNotice } from "@/components/ui/work-status";

async function openDownload(id: string) {
  const res = await api<{ url: string; authenticated?: boolean }>(`/sources/${id}/download-url`);
  if (res.authenticated || res.url.startsWith("/")) {
    const fileRes = await fetch(`${BASE_URL}${res.url}`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    if (!fileRes.ok) throw new Error("Download unavailable");
    const blob = await fileRes.blob();
    const href = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = href;
    link.download = "source";
    link.click();
    URL.revokeObjectURL(href);
    return;
  }
  window.open(res.url, "_blank");
}

export default function ImportPage() {
  const { toast } = useToast();
  const { data, loading, reload } = useApiData<{ items: Source[] }>("/sources");
  const { data: activeJobs, reload: reloadJobs } = useApiData<{ items: Job[] }>("/jobs/active");
  const [task, setTask] = useState<"file" | "text" | "url" | null>(null);
  const busy = task !== null;
  const [text, setText] = useState("");
  const [textTitle, setTextTitle] = useState("");
  const [url, setUrl] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const [activeJob, setActiveJob] = useState<string | null>(null);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [reprocessId, setReprocessId] = useState<string | null>(null);
  const [notice, setNotice] = useState<WorkNotice & { sourceId?: string } | null>(null);
  const [uploadName, setUploadName] = useState<string | null>(null);

  async function download(id: string) {
    setNotice({ phase: "progress", title: "Preparing the original file" });
    try {
      await openDownload(id);
      setNotice({ phase: "success", title: "Download started" });
    } catch (e: unknown) {
      setNotice({ phase: "error", title: "Download unavailable", detail: workError(e) });
      toast({ title: "Download unavailable", description: workError(e), variant: "error" });
    }
  }

  // Poll while any source is still running (server-side — survives browser refresh).
  useEffect(() => {
    const processing = (data?.items || []).some((s) => ["pending", "processing"].includes(s.status));
    if (!processing) return;
    const t = setInterval(() => {
      reload();
      reloadJobs();
    }, 2500);
    return () => clearInterval(t);
  }, [data, reload, reloadJobs]);

  const jobBySource = useMemo(() => {
    const map = new Map<string, Job>();
    for (const j of activeJobs?.items || []) {
      if (j.sourceId) map.set(j.sourceId, j);
    }
    return map;
  }, [activeJobs]);

  useEffect(() => {
    if (!notice?.sourceId) return;
    const source = data?.items.find((item) => item.id === notice.sourceId);
    if (!source) return;
    const job = jobBySource.get(source.id);
    const log = job?.lastLog || job?.logs?.[job.logs.length - 1]?.msg;
    const failed = source.status === "error" || job?.status === "failed";
    const finished = source.status === "done" || job?.status === "done";
    const next: WorkNotice & { sourceId?: string } = failed
      ? { phase: "error", title: `Processing failed · ${source.title}`, detail: job?.error || "The file could not be processed.", sourceId: source.id }
      : finished
        ? { phase: "success", title: `Finished · ${source.title}`, detail: `${source.stats?.wordsExtracted ?? 0} words · ${source.stats?.phrasesExtracted ?? 0} phrases extracted.`, sourceId: source.id }
        : { phase: "progress", title: source.status === "pending" ? `Queued · ${source.title}` : `Processing · ${source.title}`, detail: log || "Working in the background. You can leave and come back.", sourceId: source.id };
    setNotice((prev) => (
      prev && prev.phase === next.phase && prev.title === next.title && prev.detail === next.detail ? prev : next
    ));
  }, [data, jobBySource, notice?.sourceId]);

  async function submitText() {
    if (text.trim().length < 10) {
      setNotice({ phase: "error", title: "Add more text", detail: "Paste at least a short passage before processing." });
      return;
    }
    setTask("text");
    setNotice({ phase: "progress", title: "Sending pasted text", detail: textTitle || "Pasted text" });
    try {
      const created = await api<{ id: string }>("/sources/text", { method: "POST", body: { title: textTitle || "Pasted text", text } });
      setText(""); setTextTitle("");
      setNotice({ phase: "progress", title: "Queued · pasted text", detail: "Processing continues on the server.", sourceId: created.id });
      reload();
      reloadJobs();
    } catch (e: unknown) {
      setNotice({ phase: "error", title: "Could not process text", detail: workError(e) });
    } finally { setTask(null); }
  }

  async function submitUrl() {
    if (!url.startsWith("http")) {
      setNotice({ phase: "error", title: "Enter a valid URL", detail: "The address needs to start with http:// or https://." });
      return;
    }
    setTask("url");
    setNotice({ phase: "progress", title: "Fetching the page", detail: url });
    try {
      const created = await api<{ id: string }>("/sources/url", { method: "POST", body: { url } });
      setUrl("");
      setNotice({ phase: "progress", title: "Queued · web page", detail: "Processing continues on the server.", sourceId: created.id });
      reload();
      reloadJobs();
    } catch (e: unknown) {
      setNotice({ phase: "error", title: "Could not fetch that URL", detail: workError(e) });
    } finally { setTask(null); }
  }

  async function submitFile(file: File) {
    setTask("file");
    setUploadName(file.name);
    setNotice({ phase: "progress", title: `Uploading ${file.name}`, detail: "Stay on this page until the file is stored." });
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`${BASE_URL}/sources/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${getToken()}` },
        body: fd,
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail || "Upload failed");
      setNotice({
        phase: "progress",
        title: `Processing ${file.name}`,
        detail: "Upload finished. Extraction continues in the background.",
        sourceId: body.id,
      });
      reload();
      reloadJobs();
    } catch (e: unknown) {
      setNotice({ phase: "error", title: `Upload failed · ${file.name}`, detail: workError(e) });
    } finally { setTask(null); setUploadName(null); if (fileRef.current) fileRef.current.value = ""; }
  }

  async function reprocess(id: string, resetExtractedData = false) {
    const title = data?.items.find((item) => item.id === id)?.title || "this source";
    setNotice({
      phase: "progress",
      title: `Reprocessing · ${title}`,
      detail: resetExtractedData ? "Clearing old extracted items first." : "Using the stored file.",
      sourceId: id,
    });
    try {
      await api(`/sources/${id}/reprocess`, {
        method: "POST",
        query: { resetExtractedData },
      });
      reload();
      reloadJobs();
    } catch (e: unknown) {
      setNotice({ phase: "error", title: "Could not reprocess", detail: workError(e) });
    }
  }

  async function cancelProcessing(id: string) {
    setNotice({ phase: "progress", title: "Stopping processing" });
    try {
      await api(`/jobs/by-source/${id}/cancel`, { method: "POST" });
      setNotice({ phase: "success", title: "Processing stopped" });
      reload();
      reloadJobs();
    } catch (e: unknown) {
      setNotice({ phase: "error", title: "Could not stop", detail: workError(e) });
    }
  }

  return (
    <div className="page-stack lg:grid lg:grid-cols-2 lg:gap-6 lg:space-y-0">
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
                className={`flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed py-12 text-center transition-colors ${busy && uploadName ? "border-accent bg-accent/5" : "cursor-pointer hover:border-primary"}`}
                onClick={() => { if (!busy) fileRef.current?.click(); }}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => { e.preventDefault(); if (!busy && e.dataTransfer.files[0]) submitFile(e.dataTransfer.files[0]); }}
                aria-busy={!!(busy && uploadName)}
              >
                {busy && uploadName ? (
                  <>
                    <Loader2 className="h-10 w-10 animate-spin text-accent" />
                    <p className="font-medium">Uploading {uploadName}</p>
                    <p className="text-sm text-muted-foreground">Keep this page open until the file is stored.</p>
                  </>
                ) : (
                  <>
                <UploadCloud className="h-10 w-10 text-muted-foreground" />
                <p className="font-medium">Drop a file or click to browse</p>
                <p className="text-sm text-muted-foreground">PDF, DOCX, TXT, CSV, JSON</p>
                  </>
                )}
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
                <Button onClick={submitText} disabled={busy} className="w-full">{task === "text" ? "Sending…" : "Process text"}</Button>
              </div>
            </TabsContent>

            <TabsContent value="url">
              <div className="space-y-3">
                <div className="space-y-1.5">
                  <Label>Web page URL</Label>
                  <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" />
                </div>
                <Button onClick={submitUrl} disabled={busy} className="w-full gap-2"><Link2 className="h-4 w-4" /> {task === "url" ? "Fetching…" : "Fetch & process"}</Button>
              </div>
            </TabsContent>
          </Tabs>
          {notice && (
            <WorkStatus
              className="mt-4"
              phase={notice.phase}
              title={notice.title}
              detail={notice.detail}
              onDismiss={() => setNotice(null)}
            />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Your sources</CardTitle>
          <p className="text-sm text-muted-foreground">
            Processing runs on the server — safe to refresh or close the browser after upload. Return here anytime to
            check status.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          {loading && <p className="text-sm text-muted-foreground">Loading…</p>}
          {!loading && !data?.items.length && <p className="text-sm text-muted-foreground">No sources yet.</p>}
          {data?.items.map((s) => {
            const job = jobBySource.get(s.id);
            const lastLog = job?.lastLog || job?.logs?.[job.logs.length - 1]?.msg;
            return (
            <div key={s.id} className="rounded-lg border p-3">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:gap-3">
                <FileText className="h-5 w-5 shrink-0 text-muted-foreground sm:mt-0.5" />
                <div className="min-w-0 flex-1">
                  <button
                    type="button"
                    className="line-clamp-2 text-left font-medium hover:underline"
                    onClick={() => setPreviewId(s.id)}
                  >
                    {s.title}
                  </button>
                  <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
                    {(s.originalFileName || s.type).toString()} · {s.type.toUpperCase()} ·{" "}
                    {s.stats?.wordsExtracted ?? 0} words · {s.stats?.phrasesExtracted ?? 0} phrases
                  </p>
                </div>
              </div>
              <WorkStatus
                compact
                className="mt-3"
                {...sourceWork(s.status, s.status === "error" ? (job?.error || lastLog) : lastLog)}
              />
              <div className="mt-3 grid grid-cols-2 gap-1.5 sm:flex sm:flex-wrap">
                <Button variant="outline" size="sm" className="h-9 w-full gap-1 sm:h-8 sm:w-auto" onClick={() => setPreviewId(s.id)}>
                  <Eye className="h-3.5 w-3.5" /> Review
                </Button>
                {s.hasFile && (
                  <Button variant="outline" size="sm" className="h-9 w-full gap-1 sm:h-8 sm:w-auto" onClick={() => download(s.id)}>
                    <Download className="h-3.5 w-3.5" /> Original file
                  </Button>
                )}
                <Button variant="outline" size="sm" className="h-9 w-full gap-1 sm:h-8 sm:w-auto" onClick={() => setActiveJob(s.id)}>
                  <FileText className="h-3.5 w-3.5" /> Logs
                </Button>
                <Button variant="outline" size="sm" className="h-9 w-full gap-1 sm:h-8 sm:w-auto" onClick={() => setReprocessId(s.id)}>
                  <RefreshCw className="h-3.5 w-3.5" /> Reprocess
                </Button>
                {["pending", "processing"].includes(s.status) && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 gap-1 text-destructive hover:text-destructive"
                    onClick={() => cancelProcessing(s.id)}
                  >
                    <Square className="h-3.5 w-3.5" /> Stop
                  </Button>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 gap-1 text-destructive hover:text-destructive"
                  onClick={() => setDeleteId(s.id)}
                >
                  <Trash2 className="h-3.5 w-3.5" /> Remove
                </Button>
              </div>
            </div>
          );})}
        </CardContent>
      </Card>

      <JobLogsDialog sourceId={activeJob} onClose={() => setActiveJob(null)} />
      <SourcePreviewDialog sourceId={previewId} onClose={() => setPreviewId(null)} />
      <DeleteSourceDialog
        sourceId={deleteId}
        sourceTitle={data?.items.find((s) => s.id === deleteId)?.title}
        onClose={() => setDeleteId(null)}
        onDeleted={reload}
      />
      <ReprocessSourceDialog
        sourceId={reprocessId}
        sourceTitle={data?.items.find((s) => s.id === reprocessId)?.title}
        onClose={() => setReprocessId(null)}
        onReprocess={reprocess}
      />
    </div>
  );
}

function sourceWork(status: string, detail?: string): WorkNotice {
  if (status === "done") return { phase: "success", title: "Finished", detail: detail || "Extraction is complete." };
  if (status === "error") return { phase: "error", title: "Failed", detail: detail || "Processing did not finish." };
  if (status === "pending") return { phase: "progress", title: "Queued", detail: detail || "Waiting to start." };
  return { phase: "progress", title: "Processing", detail: detail || "Working in the background." };
}

function jobWork(job: Job | null): WorkNotice {
  if (!job) return { phase: "progress", title: "Looking up the job", detail: "Checking the latest server status." };
  if (job.status === "done") return { phase: "success", title: "Finished", detail: job.lastLog || "This job completed." };
  if (job.status === "failed" || job.status === "error") return { phase: "error", title: "Failed", detail: job.error || job.lastLog || "The job stopped with an error." };
  if (job.status === "pending") return { phase: "progress", title: "Queued", detail: job.lastLog || "Waiting for a worker." };
  return { phase: "progress", title: "Processing", detail: job.lastLog || job.error || "Working in the background." };
}

function JobLogsDialog({ sourceId, onClose }: { sourceId: string | null; onClose: () => void }) {
  const [job, setJob] = useState<Job | null>(null);
  useEffect(() => {
    if (!sourceId) return;
    let active = true;
    async function load() {
      try {
        const match = await api<Job>(`/jobs/by-source/${sourceId}`);
        if (active) setJob(match);
      } catch {
        if (active) setJob(null);
      }
    }
    load();
    const t = setInterval(load, 2500);
    return () => { active = false; clearInterval(t); };
  }, [sourceId]);

  return (
    <Dialog open={!!sourceId} onOpenChange={(v) => !v && onClose()}>
      <DialogHeader><DialogTitle>Extraction logs</DialogTitle></DialogHeader>
      <WorkStatus {...jobWork(job)} className="mb-3" />
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

function fmtBytes(n?: number) {
  if (!n) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="rounded-md border bg-secondary/30 px-3 py-2">
      <div className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="text-sm font-medium">{value}</div>
    </div>
  );
}

function SourcePreviewDialog({ sourceId, onClose }: { sourceId: string | null; onClose: () => void }) {
  const { data: source, loading } = useApiData<Source>(sourceId ? `/sources/${sourceId}` : null);
  const st = source?.stats || {};
  const num = (v?: number) => (v ?? 0).toLocaleString();
  const quality = st.qualityStatus;
  const method = st.extractionMethod;
  const warnings = (st.warnings as string[] | undefined) || [];

  return (
    <Dialog open={!!sourceId} onOpenChange={(v) => !v && onClose()}>
      <DialogHeader><DialogTitle>{source?.title || "Source detail"}</DialogTitle></DialogHeader>
      {loading || !source ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : (
        <div className="space-y-4">
          {/* Quality / extraction badges */}
          <div className="flex flex-wrap gap-2 text-xs">
            <Badge variant="secondary">{source.type.toUpperCase()}</Badge>
            {source.hasFile
              ? <Badge variant="success" className="gap-1"><CheckCircle2 className="h-3 w-3" /> S3 stored</Badge>
              : source.storage && <Badge variant="outline">stored: {source.storage}</Badge>}
            {method === "ocr" && <Badge variant="accent" className="gap-1"><ScanLine className="h-3 w-3" /> OCR Used</Badge>}
            {method === "mixed" && <Badge variant="accent" className="gap-1"><Layers className="h-3 w-3" /> Mixed Extraction</Badge>}
            {quality === "warning" && (
              <Badge variant="secondary" className="gap-1 bg-amber-500/15 text-amber-600 dark:text-amber-400">
                <AlertTriangle className="h-3 w-3" /> Warning: Low text extracted
              </Badge>
            )}
            {quality === "failed" && (
              <Badge variant="secondary" className="gap-1 bg-destructive/15 text-destructive">
                <AlertCircle className="h-3 w-3" /> Extraction failed
              </Badge>
            )}
            {quality === "ok" && (
              <Badge variant="success" className="gap-1"><CheckCircle2 className="h-3 w-3" /> Quality OK</Badge>
            )}
          </div>

          {/* Diagnostics grid */}
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            <Stat label="File type" value={source.type.toUpperCase()} />
            <Stat label="File size" value={fmtBytes(source.sizeBytes)} />
            <Stat label="Extraction" value={method || "text"} />
            <Stat label="Page count" value={num(st.pageCount)} />
            <Stat label="Embedded text pages" value={num(st.extractedPages)} />
            <Stat label="OCR pages" value={num(st.ocrPages)} />
            <Stat label="Empty pages" value={num(st.emptyPages)} />
            <Stat label="Raw text chars" value={num(st.rawTextChars ?? source.charCount)} />
            <Stat label="Cleaned text chars" value={num(st.cleanedTextChars)} />
            <Stat label="Chunks" value={num(st.chunkCount ?? source.chunkCount)} />
            <Stat label="Words extracted" value={num(st.wordsExtracted)} />
            <Stat label="Phrases extracted" value={num(st.phrasesExtracted)} />
            <Stat label="Patterns extracted" value={num(st.patternsExtracted)} />
          </div>

          {/* Warnings */}
          {warnings.length > 0 && (
            <div className="space-y-1 rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-xs">
              {warnings.map((w, i) => (
                <div key={i} className="flex items-start gap-2 text-amber-700 dark:text-amber-300">
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" /> <span>{w}</span>
                </div>
              ))}
            </div>
          )}

          {/* Extracted text preview */}
          <div>
            <div className="mb-1 text-[11px] uppercase tracking-wide text-muted-foreground">Extracted text (preview)</div>
            <div className="max-h-64 overflow-y-auto whitespace-pre-wrap rounded-md bg-secondary/50 p-3 text-sm leading-relaxed">
              {(source.rawText || "").trim() || <span className="text-muted-foreground">No extracted text yet.</span>}
            </div>
          </div>
          <p className="text-xs text-muted-foreground">Text, pages &amp; chunks are stored in MongoDB; the original file is stored in S3.</p>
          <div className="flex flex-wrap gap-2 pt-1">
            {source.hasFile && (
              <Button
                variant="outline"
                size="sm"
                className="gap-1"
                onClick={async () => {
                  try {
                    await openDownload(source.id);
                  } catch (e: any) {
                    /* parent handles via toast if needed */
                  }
                }}
              >
                <Download className="h-3.5 w-3.5" /> Download original
              </Button>
            )}
          </div>
        </div>
      )}
    </Dialog>
  );
}

function DeleteSourceDialog({
  sourceId,
  sourceTitle,
  onClose,
  onDeleted,
}: {
  sourceId: string | null;
  sourceTitle?: string;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const { toast } = useToast();
  const { data: impact, loading } = useApiData<SourceDeleteImpact>(
    sourceId ? `/sources/${sourceId}/delete-impact` : null,
  );
  const [keepData, setKeepData] = useState(true);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<WorkNotice | null>(null);

  useEffect(() => {
    if (sourceId) setKeepData(true);
  }, [sourceId]);

  async function confirm() {
    if (!sourceId) return;
    setBusy(true);
    setNotice({ phase: "progress", title: "Removing this source" });
    try {
      await api(`/sources/${sourceId}`, {
        method: "DELETE",
        query: { keepExtractedData: keepData },
      });
      toast({
        title: keepData ? "Source removed — learned items kept" : "Source and extracted data removed",
        variant: "success",
      });
      onDeleted();
      onClose();
    } catch (e: unknown) {
      setNotice({ phase: "error", title: "Could not remove this source", detail: workError(e) });
    } finally {
      setBusy(false);
    }
  }

  const linked = impact?.linked;
  const exclusive = impact?.exclusive;
  const exclusiveTotal = (exclusive?.words ?? 0) + (exclusive?.phrases ?? 0) + (exclusive?.patterns ?? 0);

  return (
    <Dialog open={!!sourceId} onOpenChange={(v) => !v && onClose()}>
      <DialogHeader>
        <DialogTitle>Remove source</DialogTitle>
        <DialogDescription>
          {sourceTitle ? `“${sourceTitle}”` : "This source"} — the original file and extracted text/chunks will be
          removed from your library.
        </DialogDescription>
      </DialogHeader>
      {loading ? (
        <p className="text-sm text-muted-foreground">Checking linked vocabulary…</p>
      ) : (
        <div className="space-y-4">
          {linked && (linked.words > 0 || linked.phrases > 0 || linked.patterns > 0) && (
            <div className="rounded-md border bg-secondary/30 p-3 text-sm">
              <p className="font-medium">Linked learned items</p>
              <p className="mt-1 text-muted-foreground">
                {linked.words} words · {linked.phrases} phrases · {linked.patterns} patterns reference this source.
              </p>
              {exclusiveTotal > 0 && (
                <p className="mt-2 text-xs text-muted-foreground">
                  {exclusiveTotal} item(s) exist only because of this source and would be deleted if you choose to
                  remove extracted data.
                </p>
              )}
            </div>
          )}

          <div className="space-y-2">
            <label className="flex cursor-pointer items-start gap-3 rounded-md border p-3 has-[:checked]:border-primary">
              <input
                type="radio"
                name="delete-mode"
                className="mt-1"
                checked={keepData}
                onChange={() => setKeepData(true)}
              />
              <span>
                <span className="font-medium">Keep learned vocabulary, phrases &amp; patterns</span>
                <span className="mt-0.5 block text-xs text-muted-foreground">
                  Remove the source and file only. Words you already extracted stay in your library (unlinked from
                  this source).
                </span>
              </span>
            </label>
            <label className="flex cursor-pointer items-start gap-3 rounded-md border p-3 has-[:checked]:border-primary">
              <input
                type="radio"
                name="delete-mode"
                className="mt-1"
                checked={!keepData}
                onChange={() => setKeepData(false)}
              />
              <span>
                <span className="font-medium">Also delete extracted data from this source</span>
                <span className="mt-0.5 block text-xs text-muted-foreground">
                  Removes words/phrases/patterns that came only from this file. Items shared with other sources are
                  kept but unlinked.
                </span>
              </span>
            </label>
          </div>

          {notice && <WorkStatus phase={notice.phase} title={notice.title} detail={notice.detail} />}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose} disabled={busy}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={confirm} disabled={busy}>
              {busy ? "Removing…" : "Remove source"}
            </Button>
          </div>
        </div>
      )}
    </Dialog>
  );
}

function ReprocessSourceDialog({
  sourceId,
  sourceTitle,
  onClose,
  onReprocess,
}: {
  sourceId: string | null;
  sourceTitle?: string;
  onClose: () => void;
  onReprocess: (id: string, resetExtractedData: boolean) => Promise<void>;
}) {
  const [clearData, setClearData] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<WorkNotice | null>(null);

  useEffect(() => {
    if (sourceId) setClearData(false);
  }, [sourceId]);

  async function confirm() {
    if (!sourceId) return;
    setBusy(true);
    setNotice({ phase: "progress", title: "Starting reprocess" });
    try {
      await onReprocess(sourceId, clearData);
      onClose();
    } catch (e: unknown) {
      setNotice({ phase: "error", title: "Could not start reprocess", detail: workError(e) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={!!sourceId} onOpenChange={(v) => !v && onClose()}>
      <DialogHeader>
        <DialogTitle>Reprocess source</DialogTitle>
        <DialogDescription>
          Re-run text extraction on {sourceTitle ? `“${sourceTitle}”` : "this source"} using the stored file or text.
        </DialogDescription>
      </DialogHeader>
      <div className="space-y-4">
        <label className="flex cursor-pointer items-start gap-3 rounded-md border p-3">
          <input
            type="checkbox"
            className="mt-1"
            checked={clearData}
            onChange={(e) => setClearData(e.target.checked)}
          />
          <span>
            <span className="font-medium">Clear old extracted items first</span>
            <span className="mt-0.5 block text-xs text-muted-foreground">
              Delete vocabulary/phrases/patterns that belong only to this source before re-extracting. Leave unchecked
              to keep existing learned items and merge new results.
            </span>
          </span>
        </label>
        {notice && <WorkStatus phase={notice.phase} title={notice.title} detail={notice.detail} />}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={confirm} disabled={busy}>
            {busy ? "Starting…" : "Reprocess"}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
