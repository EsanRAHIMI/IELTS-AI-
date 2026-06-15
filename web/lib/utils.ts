import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function priorityColor(score: number): string {
  if (score >= 80) return "text-accent-foreground bg-accent";
  if (score >= 60) return "text-success-foreground bg-success";
  if (score >= 40) return "bg-secondary text-secondary-foreground";
  return "bg-muted text-muted-foreground";
}

export function statusLabel(status: string): string {
  return ({ new: "New", learning: "Learning", review: "Review", mastered: "Mastered" } as Record<string, string>)[status] || status;
}

export function classNamesForStatus(status: string): string {
  return (
    {
      new: "bg-secondary text-secondary-foreground",
      learning: "bg-accent/20 text-accent-foreground",
      review: "bg-primary/10 text-primary",
      mastered: "bg-success/15 text-success",
    } as Record<string, string>
  )[status] || "bg-muted text-muted-foreground";
}
