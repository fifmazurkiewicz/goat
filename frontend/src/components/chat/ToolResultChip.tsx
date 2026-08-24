import { Badge } from "@/components/ui/badge";
import { toolChipLabel } from "@/lib/chat-status";
import { cn } from "@/lib/utils";
import type { ChatStreamToolResultEvent } from "@/types/chat-stream";

/** Inline chip from a real-time `tool_result` event (docs/technical/frontend.md section 4). */
export function ToolResultChip({ tool_name, summary, success }: ChatStreamToolResultEvent) {
  return (
    <div
      className={cn(
        "flex max-w-[80%] items-center gap-2 self-start rounded-md border px-3 py-2 text-xs",
        !success && "border-destructive/50 text-destructive"
      )}
    >
      <Badge variant={success ? "default" : "destructive"}>{toolChipLabel(tool_name)}</Badge>
      <span>{summary}</span>
    </div>
  );
}
