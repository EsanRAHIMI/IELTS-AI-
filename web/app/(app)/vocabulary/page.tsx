"use client";

import { useState } from "react";
import { Search, Star, EyeOff, Plus, RefreshCw, Eye } from "lucide-react";
import { api } from "@/lib/api";
import { useApiData } from "@/hooks/useApiData";
import type { Paginated, Word } from "@/types";
import { cn, priorityColor, classNamesForStatus } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Sheet, SheetBody } from "@/components/ui/sheet";
import { Pagination } from "@/components/ui/pagination";
import { useToast } from "@/components/ui/toast";

const SECTIONS = ["Writing Task 1", "Writing Task 2", "Reading", "Listening", "Speaking"];
const DIFFICULTIES = ["A2", "B1", "B2", "C1", "C2"];
const STATUSES = ["new", "learning", "review", "mastered"];
const POS = ["noun", "verb", "adjective", "adverb"];

export default function VocabularyPage() {
  const { toast } = useToast();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [section, setSection] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [status, setStatus] = useState("");
  const [pos, setPos] = useState("");
  const [minPriority, setMinPriority] = useState(0);
  const [detail, setDetail] = useState<string | null>(null);

  const query = { page, limit: 25, search, section, difficulty, status, pos, minPriority };
  const { data, loading, reload } = useApiData<Paginated<Word>>("/vocabulary", query);
  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.limit)) : 1;

  async function addToStudy(w: Word) {
    await api("/study/cards", { method: "POST", body: { type: "word", refId: w.id } });
    toast({ title: `Added "${w.word}" to study`, variant: "success" });
    reload();
  }
  async function toggleImportant(w: Word) {
    await api(`/vocabulary/${w.id}/important`, { method: "PATCH" });
    reload();
  }
  async function hide(w: Word) {
    await api(`/vocabulary/${w.id}/hide`, { method: "PATCH" });
    toast({ title: "Hidden" });
    reload();
  }

  return (
    <div className="page-stack">
      <Card>
        <CardContent className="grid grid-cols-1 gap-3 p-4 sm:grid-cols-2 xl:grid-cols-3">
          <div className="relative sm:col-span-2 xl:col-span-1">
            <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input className="pl-8" placeholder="Search words…" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
          </div>
          <Select value={section} onChange={(e) => { setSection(e.target.value); setPage(1); }}>
            <option value="">All sections</option>
            {SECTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
          </Select>
          <Select value={difficulty} onChange={(e) => { setDifficulty(e.target.value); setPage(1); }}>
            <option value="">All levels</option>
            {DIFFICULTIES.map((d) => <option key={d} value={d}>{d}</option>)}
          </Select>
          <Select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
            <option value="">All statuses</option>
            {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </Select>
          <Select value={pos} onChange={(e) => { setPos(e.target.value); setPage(1); }}>
            <option value="">All POS</option>
            {POS.map((p) => <option key={p} value={p}>{p}</option>)}
          </Select>
        </CardContent>
      </Card>

      {/* Mobile: card list */}
      <div className="space-y-3 lg:hidden">
        {loading && <p className="py-8 text-center text-sm text-muted-foreground">Loading…</p>}
        {!loading && !data?.items.length && (
          <Card><CardContent className="py-10 text-center text-sm text-muted-foreground">No words found. Import a source or seed data.</CardContent></Card>
        )}
        {data?.items.map((w) => (
          <WordMobileCard
            key={w.id}
            word={w}
            onDetail={() => setDetail(w.id)}
            onStudy={() => addToStudy(w)}
            onImportant={() => toggleImportant(w)}
            onHide={() => hide(w)}
          />
        ))}
        {!loading && !!data?.items.length && (
          <Pagination page={page} totalPages={totalPages} total={data.total} label="words" onPageChange={setPage} />
        )}
      </div>

      {/* Desktop: table */}
      <Card className="hidden min-w-0 lg:block">
        <div className="min-w-0 overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Word</TableHead>
                <TableHead className="w-20">Freq</TableHead>
                <TableHead className="w-24">Priority</TableHead>
                <TableHead>Meaning</TableHead>
                <TableHead className="hidden xl:table-cell">IELTS use</TableHead>
                <TableHead className="w-20">Level</TableHead>
                <TableHead className="w-24">Status</TableHead>
                <TableHead className="w-36 text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading && <TableRow><TableCell colSpan={8} className="py-10 text-center text-muted-foreground">Loading…</TableCell></TableRow>}
              {!loading && !data?.items.length && <TableRow><TableCell colSpan={8} className="py-10 text-center text-muted-foreground">No words found.</TableCell></TableRow>}
              {data?.items.map((w) => (
                <TableRow key={w.id}>
                  <TableCell>
                    <button onClick={() => setDetail(w.id)} className="flex items-center gap-2 font-medium hover:underline">
                      {w.important && <Star className="h-3.5 w-3.5 fill-accent text-accent" />}
                      {w.word}
                    </button>
                    <span className="block text-xs text-muted-foreground">{w.partOfSpeech}</span>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{w.frequency}</TableCell>
                  <TableCell>
                    <span className={cn("inline-flex h-7 w-9 items-center justify-center rounded-md text-xs font-bold", priorityColor(w.priorityScore))}>
                      {w.priorityScore}
                    </span>
                  </TableCell>
                  <TableCell className="max-w-[220px]">
                    <span className="block truncate text-sm">{w.simpleEnglishMeaning || "—"}</span>
                    {w.persianMeaning && <span className="farsi block truncate text-xs text-muted-foreground">{w.persianMeaning}</span>}
                  </TableCell>
                  <TableCell className="hidden xl:table-cell">
                    <div className="flex flex-wrap gap-1">{(w.ieltsUseCases || []).slice(0, 2).map((u) => <Badge key={u} variant="secondary" className="text-[10px]">{u}</Badge>)}</div>
                  </TableCell>
                  <TableCell><Badge variant="outline">{w.difficulty}</Badge></TableCell>
                  <TableCell><Badge className={cn("border-0", classNamesForStatus(w.status))}>{w.status}</Badge></TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-0.5">
                      <Button variant="ghost" size="icon" title="Detail" onClick={() => setDetail(w.id)}><Eye className="h-4 w-4" /></Button>
                      <Button variant="ghost" size="icon" title="Add to study" onClick={() => addToStudy(w)}><Plus className="h-4 w-4" /></Button>
                      <Button variant="ghost" size="icon" title="Mark important" onClick={() => toggleImportant(w)}><Star className={cn("h-4 w-4", w.important && "fill-accent text-accent")} /></Button>
                      <Button variant="ghost" size="icon" title="Hide" onClick={() => hide(w)}><EyeOff className="h-4 w-4" /></Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
        {!loading && !!data?.items.length && (
          <div className="px-4 pb-4">
            <Pagination page={page} totalPages={totalPages} total={data.total} label="words" onPageChange={setPage} />
          </div>
        )}
      </Card>

      <WordDetailSheet id={detail} onClose={() => setDetail(null)} onChanged={reload} />
    </div>
  );
}

function WordMobileCard({
  word: w,
  onDetail,
  onStudy,
  onImportant,
  onHide,
}: {
  word: Word;
  onDetail: () => void;
  onStudy: () => void;
  onImportant: () => void;
  onHide: () => void;
}) {
  return (
    <Card className="overflow-hidden">
      <CardContent className="p-4">
        <button type="button" onClick={onDetail} className="w-full text-left">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                {w.important && <Star className="h-4 w-4 shrink-0 fill-accent text-accent" />}
                <span className="truncate text-lg font-semibold">{w.word}</span>
              </div>
              <p className="mt-0.5 text-xs text-muted-foreground">{w.partOfSpeech} · freq {w.frequency}</p>
            </div>
            <span className={cn("inline-flex h-8 w-10 shrink-0 items-center justify-center rounded-lg text-xs font-bold", priorityColor(w.priorityScore))}>
              {w.priorityScore}
            </span>
          </div>
          {(w.simpleEnglishMeaning || w.persianMeaning) && (
            <div className="mt-2 space-y-0.5">
              {w.simpleEnglishMeaning && <p className="text-sm leading-snug text-muted-foreground">{w.simpleEnglishMeaning}</p>}
              {w.persianMeaning && <p className="farsi text-sm leading-snug">{w.persianMeaning}</p>}
            </div>
          )}
          <div className="mt-2 flex flex-wrap gap-1.5">
            <Badge variant="outline" className="text-[10px]">{w.difficulty}</Badge>
            <Badge className={cn("border-0 text-[10px]", classNamesForStatus(w.status))}>{w.status}</Badge>
          </div>
        </button>
        <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Button variant="outline" size="sm" className="h-9 gap-1.5" onClick={onDetail}><Eye className="h-3.5 w-3.5" /> View</Button>
          <Button variant="outline" size="sm" className="h-9 gap-1.5" onClick={onStudy}><Plus className="h-3.5 w-3.5" /> Study</Button>
          <Button variant="outline" size="sm" className="h-9 gap-1.5" onClick={onImportant}>
            <Star className={cn("h-3.5 w-3.5", w.important && "fill-accent text-accent")} /> Star
          </Button>
          <Button variant="outline" size="sm" className="h-9 gap-1.5 text-muted-foreground" onClick={onHide}><EyeOff className="h-3.5 w-3.5" /> Hide</Button>
        </div>
      </CardContent>
    </Card>
  );
}

function WordDetailSheet({ id, onClose, onChanged }: { id: string | null; onClose: () => void; onChanged: () => void }) {
  const { toast } = useToast();
  const { data: word, loading, reload } = useApiData<Word>(id ? `/vocabulary/${id}` : null);
  const [busy, setBusy] = useState(false);

  async function regenerate() {
    if (!id) return;
    setBusy(true);
    try {
      await api(`/vocabulary/${id}/regenerate`, { method: "POST" });
      toast({ title: "AI explanation regenerated", variant: "success" });
      reload();
    } catch (e: any) {
      toast({ title: "Failed", description: e.message, variant: "error" });
    } finally { setBusy(false); }
  }
  async function addToStudy() {
    if (!id) return;
    await api("/study/cards", { method: "POST", body: { type: "word", refId: id } });
    toast({ title: "Added to study", variant: "success" });
    onChanged();
  }

  return (
    <Sheet open={!!id} onOpenChange={(v) => !v && onClose()}>
      <SheetBody>
        {loading || !word ? (
          <p className="text-muted-foreground">Loading…</p>
        ) : (
          <div className="min-w-0 space-y-5">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-2xl font-bold break-words">{word.word}</h2>
                <Badge variant="outline">{word.partOfSpeech}</Badge>
                <Badge variant="outline">{word.difficulty}</Badge>
              </div>
              <span className={cn("mt-2 inline-flex items-center rounded-md px-2 py-0.5 text-xs font-bold", priorityColor(word.priorityScore))}>Priority {word.priorityScore}</span>
            </div>

            {word.persianMeaning && (
              <Field label="Persian meaning"><p className="farsi text-base break-words">{word.persianMeaning}</p></Field>
            )}
            {word.simpleEnglishMeaning && <Field label="Simple English meaning"><p className="break-words">{word.simpleEnglishMeaning}</p></Field>}

            {!!word.collocations?.length && (
              <Field label="Collocations">
                <div className="flex flex-wrap gap-2">{word.collocations.map((c) => <Badge key={c} variant="secondary">{c}</Badge>)}</div>
              </Field>
            )}
            {!!word.examples?.length && (
              <Field label="Examples">
                <ul className="space-y-1.5">{word.examples.map((e, i) => <li key={i} className="rounded-md bg-secondary/50 p-2 text-sm break-words">{e}</li>)}</ul>
              </Field>
            )}
            {!!word.ieltsUseCases?.length && (
              <Field label="IELTS use cases"><div className="flex flex-wrap gap-2">{word.ieltsUseCases.map((u) => <Badge key={u} variant="accent">{u}</Badge>)}</div></Field>
            )}
            {!!word.commonMistakes?.length && (
              <Field label="Common mistakes"><ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">{word.commonMistakes.map((m, i) => <li key={i} className="break-words">{m}</li>)}</ul></Field>
            )}
            {word.notes && <Field label="AI notes"><p className="text-sm text-muted-foreground break-words">{word.notes}</p></Field>}
            {!!word.sources?.length && (
              <Field label="Sources"><div className="flex flex-wrap gap-2">{word.sources.map((s) => <Badge key={s.id} variant="outline">{s.title}</Badge>)}</div></Field>
            )}

            <div className="flex flex-col gap-2 pt-2 sm:flex-row">
              <Button onClick={addToStudy} className="flex-1 gap-2"><Plus className="h-4 w-4" /> Add to flashcards</Button>
              <Button variant="outline" onClick={regenerate} disabled={busy} className="flex-1 gap-2 sm:flex-none"><RefreshCw className={cn("h-4 w-4", busy && "animate-spin")} /> Regenerate</Button>
            </div>
          </div>
        )}
      </SheetBody>
    </Sheet>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
      {children}
    </div>
  );
}
