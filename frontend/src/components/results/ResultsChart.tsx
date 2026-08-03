import { useMemo } from "react";
import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";
import { format } from "date-fns";
import { pl } from "date-fns/locale";

import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import type { Result } from "@/types/api";

interface ResultsChartProps {
  results: Result[];
  metric: string;
}

const chartConfig: ChartConfig = {
  value: { label: "Wartość", color: "hsl(var(--primary))" },
};

/** Wykres liniowy per metryka (`recharts` przez shadcn `Chart`) — docs/technical/frontend.md sekcja 6, ADR-9. */
export function ResultsChart({ results, metric }: ResultsChartProps) {
  const data = useMemo(
    () =>
      results
        .filter((r) => r.metric === metric)
        .sort((a, b) => a.logged_date.localeCompare(b.logged_date))
        .map((r) => ({
          date: format(new Date(r.logged_date), "d MMM", { locale: pl }),
          value: r.value,
        })),
    [results, metric]
  );

  if (data.length === 0) {
    return <p className="text-sm text-muted-foreground">Brak danych do wykresu dla tej metryki.</p>;
  }

  return (
    <ChartContainer config={chartConfig} className="h-64 w-full">
      <LineChart data={data} margin={{ left: 12, right: 12, top: 8, bottom: 8 }}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="date" tickLine={false} axisLine={false} />
        <YAxis tickLine={false} axisLine={false} width={40} />
        <ChartTooltip content={<ChartTooltipContent />} />
        <Line type="monotone" dataKey="value" stroke="var(--color-value)" strokeWidth={2} dot={{ r: 3 }} />
      </LineChart>
    </ChartContainer>
  );
}
