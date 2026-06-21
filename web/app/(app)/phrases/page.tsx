"use client";

import { useState } from "react";
import { Search, Plus, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { useApiData } from "@/hooks/useApiData";
import type { Paginated, Phrase } from "@/types";
import { cn, priorityColor } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Pagination } from "@/components/ui/pagination";
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
    <div className="page-stack">
      <Card>
        <CardContent className="grid grid-cols-1 gap-3 p-4 sm:grid-cols-2">
          <div className="relative min-w-0">
            <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input className="pl-8" placeholder="Search phrases…" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
          </div>
          <Select value={section} onChange={(e) => { setSection(e.target.value); setPage(1); }}>
            <option value="">All sections</option>
            {SECTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
          </Select>
        </CardContent>
      </Card>

      {loading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {!loading && !data?.items.length && <p className="text-sm text-muted-foreground">No phrases yet.</p>}

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {data?.items.map((p) => (
          <Card key={p.id}>
            <CardContent className="p-4">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <p className="break-words font-semibold leading-snug">{p.phrase}</p>
                  <Badge variant="secondary" className="mt-1 max-w-full truncate text-[10px]">{p.section}</Badge>
                </div>
                <span className={cn("inline-flex h-7 w-9 shrink-0 items-center justify-center rounded-md text-xs font-bold", priorityColor(p.priorityScore))}>{p.priorityScore}</span>
              </div>
              {p.simpleEnglishMeaning && <p className="mt-2 break-words text-sm text-muted-foreground">{p.simpleEnglishMeaning}</p>}
              {p.persianMeaning && <p className="farsi mt-1 break-words text-sm">{p.persianMeaning}</p>}
              {!!p.examples?.length && <p className="mt-2 break-words rounded-md bg-secondary/50 p-2 text-sm italic">{p.examples[0]}</p>}
              <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                <Button size="sm" variant="outline" className="h-9 flex-1 gap-1.5" onClick={() => addToStudy(p)}><Plus className="h-3.5 w-3.5" /> Study</Button>
                <Button size="sm" variant="ghost" className="h-9 flex-1 gap-1.5" onClick={() => regenerate(p)}><RefreshCw className="h-3.5 w-3.5" /> Regenerate</Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {!loading && (data?.total ?? 0) > 0 && (
        <Pagination page={page} totalPages={totalPages} total={data?.total ?? 0} label="phrases" onPageChange={setPage} />
      )}
    </div>
  );
}
