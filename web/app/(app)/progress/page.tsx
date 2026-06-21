"use client";

import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  Legend,
} from "recharts";
import { useApiData } from "@/hooks/useApiData";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface ProgressData {
  timeline: { date: string; reviews: number; correct: number; accuracy: number }[];
  totalReviews: number;
  accuracy: number;
  statusDistribution: Record<string, number>;
  sourceCoverage: { title: string; words: number; phrases: number }[];
}

const STATUS_COLORS: Record<string, string> = {
  new: "#94a3b8",
  learning: "#f59e0b",
  review: "#3b82f6",
  mastered: "#22c55e",
};

export default function ProgressPage() {
  const { data, loading } = useApiData<ProgressData>("/progress", { days: 30 });

  if (loading) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (!data) return null;

  const pieData = Object.entries(data.statusDistribution).map(([k, v]) => ({ name: k, value: v }));
  const hasReviews = data.totalReviews > 0;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Total reviews (30d)" value={data.totalReviews} />
        <Stat label="Review accuracy" value={`${data.accuracy}%`} />
        <Stat label="Mastered cards" value={data.statusDistribution.mastered ?? 0} />
      </div>

      <Card>
        <CardHeader><CardTitle>Review activity & accuracy</CardTitle></CardHeader>
        <CardContent className="h-72">
          {hasReviews ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.timeline}>
                <defs>
                  <linearGradient id="rev" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
                <YAxis tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
                <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8 }} />
                <Area type="monotone" dataKey="reviews" stroke="hsl(var(--primary))" fill="url(#rev)" name="Reviews" />
                <Area type="monotone" dataKey="accuracy" stroke="hsl(var(--accent))" fillOpacity={0} name="Accuracy %" />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <Empty>Review some flashcards to see your activity here.</Empty>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Card status distribution</CardTitle></CardHeader>
          <CardContent className="h-64">
            {pieData.some((d) => d.value > 0) ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                    {pieData.map((d) => <Cell key={d.name} fill={STATUS_COLORS[d.name] || "#999"} />)}
                  </Pie>
                  <Legend />
                  <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8 }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <Empty>No cards yet. Add some from Vocabulary.</Empty>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Source coverage</CardTitle></CardHeader>
          <CardContent className="h-64">
            {data.sourceCoverage.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.sourceCoverage.slice(0, 8)} layout="vertical" margin={{ left: 4, right: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis type="number" tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
                  <YAxis
                    type="category"
                    dataKey="title"
                    width={72}
                    tick={{ fontSize: 10 }}
                    stroke="hsl(var(--muted-foreground))"
                    tickFormatter={(v: string) => (v.length > 12 ? `${v.slice(0, 12)}…` : v)}
                  />
                  <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8 }} />
                  <Bar dataKey="words" fill="hsl(var(--primary))" name="Words" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <Empty>Import sources to see coverage.</Empty>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <Card><CardContent className="p-6"><p className="text-sm text-muted-foreground">{label}</p><p className="mt-1 text-3xl font-bold">{value}</p></CardContent></Card>
  );
}
function Empty({ children }: { children: React.ReactNode }) {
  return <div className="flex h-full items-center justify-center text-sm text-muted-foreground">{children}</div>;
}
