import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function Pagination({
  page,
  totalPages,
  total,
  label,
  onPageChange,
  className,
}: {
  page: number;
  totalPages: number;
  total: number;
  label: string;
  onPageChange: (page: number) => void;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-3 border-t pt-4 sm:flex-row sm:items-center sm:justify-between", className)}>
      <span className="text-center text-sm text-muted-foreground sm:text-left">
        {total.toLocaleString()} {label}
      </span>
      <div className="flex items-center justify-center gap-2">
        <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onPageChange(page - 1)} aria-label="Previous page">
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <span className="min-w-[5.5rem] text-center text-sm tabular-nums">
          {page} / {totalPages}
        </span>
        <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)} aria-label="Next page">
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
