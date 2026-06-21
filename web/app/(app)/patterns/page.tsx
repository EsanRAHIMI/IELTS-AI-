"use client";

import { useState } from "react";
import { Search, Plus, Copy } from "lucide-react";
import { api } from "@/lib/api";
import { useApiData } from "@/hooks/useApiData";
import type { Paginated, Pattern } from "@/types";
import { cn, priorityColor } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Pagination } from "@/components/ui/pagination";
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
    <div className="page-stack">
      <Card>
        <CardContent className="grid grid-cols-1 gap-3 p-4">
          <div className="relative min-w-0">
            <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input className="pl-8" placeholder="Search patterns…" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
          </div>
          <Select value={category} onChange={(e) => { setCategory(e.target.value); setPage(1); }}>
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
              <div className="flex flex-wrap items-start justify-between gap-2">
                <Badge variant="accent" className="max-w-full truncate text-[10px]">{p.category}</Badge>
                <span className={cn("inline-flex h-7 w-9 shrink-0 items-center justify-center rounded-md text-xs font-bold", priorityColor(p.priorityScore))}>{p.priorityScore}</span>
              </div>
              <p className="mt-3 break-words font-medium leading-relaxed">{p.template}</p>
              {p.sentence && p.sentence !== p.template && (
                <p className="mt-2 break-words rounded-md bg-secondary/50 p-2 text-sm italic text-muted-foreground">e.g. {p.sentence}</p>
              )}
              {p.notes && <p className="mt-2 break-words text-sm text-muted-foreground">{p.notes}</p>}
              <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                <Button size="sm" variant="outline" className="h-9 flex-1 gap-1.5" onClick={() => addToStudy(p)}><Plus className="h-3.5 w-3.5" /> Study</Button>
                <Button size="sm" variant="ghost" className="h-9 flex-1 gap-1.5" onClick={() => copy(p.template)}><Copy className="h-3.5 w-3.5" /> Copy</Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {!loading && (data?.total ?? 0) > 0 && (
        <Pagination page={page} totalPages={totalPages} total={data?.total ?? 0} label="patterns" onPageChange={setPage} />
      )}
    </div>
  );
}
