"use client";

import { useState } from "react";
import { Search, Plus, ChevronLeft, ChevronRight, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { useApiData } from "@/hooks/useApiData";
import type { Paginated, Phrase } from "@/types";
import { cn, priorityColor } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";

const SECTIONS = ["Writing Task 1", "Writing Task 2", "Reading", "Listening", "Speaking"];

export default function PhrasesPage() {
  const { toast } = useToast();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [section, setSection] = useState("");
  const query = { page, limit: 24, search, section };
  const { data, loading, reload } = useApiData<Paginated<Phrase>>("/phrases", query);
  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.limit)) : 1;

  async function addToStudy(p: Phrase) {
    await api("/study/cards", { method: "POST", body: { type: "phrase", refId: p.id } });
    toast({ title: "Added to study", variant: "success" });
  }
  async function regenerate(p: Phrase) {
    await api(`/phrases/${p.id}/regenerate`, { method: "POST" });
    toast({ title: "Regenerated", variant: "success" });
    reload();
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="flex flex-col gap-3 p-4 sm:flex-row">
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input className="pl-8" placeholder="Search phrases…" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
          </div>
          <Select className="sm:w-56" value={section} onChange={(e) => { setSection(e.target.value); setPage(1); }}>
            <option value="">All sections</option>
            {SECTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
          </Select>
        </CardContent>
      </Card>

      {loading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {!loading && !data?.items.length && <p className="text-sm text-muted-foreground">No phrases yet.</p>}

      <div className="grid gap-3 md:grid-cols-2">
        {data?.items.map((p) => (
          <Card key={p.id}>
            <CardContent className="p-4">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="font-semibold">{p.phrase}</p>
                  <Badge variant="secondary" className="mt-1 text-[10px]">{p.section}</Badge>
                </div>
                <span className={cn("inline-flex h-7 w-9 shrink-0 items-center justify-center rounded-md text-xs font-bold", priorityColor(p.priorityScore))}>{p.priorityScore}</span>
              </div>
              {p.simpleEnglishMeaning && <p className="mt-2 text-sm text-muted-foreground">{p.simpleEnglishMeaning}</p>}
              {p.persianMeaning && <p className="farsi mt-1 text-sm">{p.persianMeaning}</p>}
              {!!p.examples?.length && <p className="mt-2 rounded-md bg-secondary/50 p-2 text-sm italic">{p.examples[0]}</p>}
              <div className="mt-3 flex gap-2">
                <Button size="sm" variant="outline" className="gap-1.5" onClick={() => addToStudy(p)}><Plus className="h-3.5 w-3.5" /> Study</Button>
                <Button size="sm" variant="ghost" className="gap-1.5" onClick={() => regenerate(p)}><RefreshCw className="h-3.5 w-3.5" /> Regenerate</Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">{data?.total ?? 0} phrases</span>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}><ChevronLeft className="h-4 w-4" /></Button>
          <span>Page {page} / {totalPages}</span>
          <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}><ChevronRight className="h-4 w-4" /></Button>
        </div>
      </div>
    </div>
  );
}
