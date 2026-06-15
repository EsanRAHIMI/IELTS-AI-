"use client";

import { useState } from "react";
import { Search, Plus, Copy, ChevronLeft, ChevronRight } from "lucide-react";
import { api } from "@/lib/api";
import { useApiData } from "@/hooks/useApiData";
import type { Paginated, Pattern } from "@/types";
import { cn, priorityColor } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";

const CATEGORIES = [
  "Writing Task 1 trend description",
  "Writing Task 1 comparison",
  "Writing Task 2 opinion",
  "Writing Task 2 cause/effect",
  "Writing Task 2 advantage/disadvantage",
  "Speaking fluency phrases",
  "Speaking personal experience phrases",
  "Reading academic structures",
  "Listening functional phrases",
];

export default function PatternsPage() {
  const { toast } = useToast();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const query = { page, limit: 20, search, category };
  const { data, loading } = useApiData<Paginated<Pattern>>("/patterns", query);
  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.limit)) : 1;

  async function addToStudy(p: Pattern) {
    await api("/study/cards", { method: "POST", body: { type: "sentence_pattern", refId: p.id } });
    toast({ title: "Added to study", variant: "success" });
  }
  function copy(text: string) {
    navigator.clipboard?.writeText(text);
    toast({ title: "Copied template" });
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="flex flex-col gap-3 p-4 sm:flex-row">
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input className="pl-8" placeholder="Search patterns…" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
          </div>
          <Select className="sm:w-72" value={category} onChange={(e) => { setCategory(e.target.value); setPage(1); }}>
            <option value="">All categories</option>
            {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </Select>
        </CardContent>
      </Card>

      {loading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {!loading && !data?.items.length && <p className="text-sm text-muted-foreground">No sentence patterns yet.</p>}

      <div className="space-y-3">
        {data?.items.map((p) => (
          <Card key={p.id}>
            <CardContent className="p-4">
              <div className="flex items-start justify-between gap-3">
                <Badge variant="accent">{p.category}</Badge>
                <span className={cn("inline-flex h-7 w-9 shrink-0 items-center justify-center rounded-md text-xs font-bold", priorityColor(p.priorityScore))}>{p.priorityScore}</span>
              </div>
              <p className="mt-3 font-medium leading-relaxed">{p.template}</p>
              {p.sentence && p.sentence !== p.template && (
                <p className="mt-2 rounded-md bg-secondary/50 p-2 text-sm italic text-muted-foreground">e.g. {p.sentence}</p>
              )}
              {p.notes && <p className="mt-2 text-sm text-muted-foreground">{p.notes}</p>}
              <div className="mt-3 flex gap-2">
                <Button size="sm" variant="outline" className="gap-1.5" onClick={() => addToStudy(p)}><Plus className="h-3.5 w-3.5" /> Study</Button>
                <Button size="sm" variant="ghost" className="gap-1.5" onClick={() => copy(p.template)}><Copy className="h-3.5 w-3.5" /> Copy</Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">{data?.total ?? 0} patterns</span>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}><ChevronLeft className="h-4 w-4" /></Button>
          <span>Page {page} / {totalPages}</span>
          <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}><ChevronRight className="h-4 w-4" /></Button>
        </div>
      </div>
    </div>
  );
}
