import { cn } from "@/lib/utils";

interface StreamingStatusLineProps {
  label: string;
  className?: string;
}

/** Single status line shown during stream silence (routing / thinking / tool) — disappears when tokens arrive. */
export function StreamingStatusLine({ label, className }: StreamingStatusLineProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "flex max-w-[85%] items-center gap-2 self-start text-sm text-muted-foreground",
        className
      )}
    >
      <span
        className="inline-block size-1.5 shrink-0 animate-pulse rounded-full bg-muted-foreground/70"
        aria-hidden
      />
      <span>{label}</span>
    </div>
  );
}
