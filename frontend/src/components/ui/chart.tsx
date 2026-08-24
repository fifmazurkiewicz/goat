import * as React from "react";
import * as RechartsPrimitive from "recharts";

import { cn } from "@/lib/utils";

export type ChartConfig = Record<
  string,
  {
    label?: React.ReactNode;
    color?: string;
  }
>;

type ChartContextProps = { config: ChartConfig };
const ChartContext = React.createContext<ChartContextProps | null>(null);

function useChart() {
  const context = React.useContext(ChartContext);
  if (!context) throw new Error("useChart must be used inside <ChartContainer />");
  return context;
}

/**
 * Thin wrapper around `recharts` (docs/technical/frontend.md section 6, ADR-9) —
 * sets `--color-{key}` CSS variables from `config` so the charts inherit the
 * consistent shadcn/ui styling instead of hard-coded recharts colors.
 */
const ChartContainer = React.forwardRef<
  HTMLDivElement,
  React.ComponentProps<"div"> & {
    config: ChartConfig;
    children: React.ComponentProps<typeof RechartsPrimitive.ResponsiveContainer>["children"];
  }
>(({ id, className, children, config, ...props }, ref) => {
  const generatedId = React.useId().replace(/:/g, "");
  const chartId = `chart-${id ?? generatedId}`;
  const style = Object.fromEntries(
    Object.entries(config)
      .filter(([, cfg]) => cfg.color)
      .map(([key, cfg]) => [`--color-${key}`, cfg.color])
  ) as React.CSSProperties;

  return (
    <ChartContext.Provider value={{ config }}>
      <div
        data-chart={chartId}
        ref={ref}
        className={cn(
          "flex aspect-video justify-center text-xs [&_.recharts-cartesian-axis-tick_text]:fill-muted-foreground [&_.recharts-cartesian-grid_line]:stroke-border [&_.recharts-dot]:stroke-transparent [&_.recharts-layer]:outline-none [&_.recharts-sector]:outline-none [&_.recharts-surface]:outline-none",
          className
        )}
        style={style}
        {...props}
      >
        <RechartsPrimitive.ResponsiveContainer>{children}</RechartsPrimitive.ResponsiveContainer>
      </div>
    </ChartContext.Provider>
  );
});
ChartContainer.displayName = "ChartContainer";

const ChartTooltip = RechartsPrimitive.Tooltip;

const ChartTooltipContent = React.forwardRef<
  HTMLDivElement,
  React.ComponentProps<typeof RechartsPrimitive.Tooltip> & React.ComponentProps<"div"> & { labelKey?: string }
>(({ active, payload, className, label }, ref) => {
  const { config } = useChart();

  if (!active || !payload?.length) return null;

  return (
    <div
      ref={ref}
      className={cn(
        "grid min-w-[8rem] items-start gap-1.5 rounded-lg border border-border/50 bg-background px-2.5 py-1.5 text-xs shadow-xl",
        className
      )}
    >
      {label ? <div className="font-medium">{label}</div> : null}
      <div className="grid gap-1.5">
        {payload.map((item, index) => {
          const key = String(item.dataKey ?? item.name ?? index);
          const cfg = config[key];
          return (
            <div key={key} className="flex w-full items-center gap-2">
              <span
                className="h-2.5 w-2.5 shrink-0 rounded-[2px]"
                style={{ backgroundColor: (item.color as string) ?? cfg?.color }}
              />
              <div className="flex flex-1 justify-between leading-none">
                <span className="text-muted-foreground">{cfg?.label ?? item.name}</span>
                <span className="font-mono font-medium tabular-nums text-foreground">
                  {typeof item.value === "number" ? item.value.toLocaleString("pl-PL") : item.value}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
});
ChartTooltipContent.displayName = "ChartTooltipContent";

export { ChartContainer, ChartTooltip, ChartTooltipContent, useChart };
