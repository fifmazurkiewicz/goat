import { useResultsByDate } from "@/hooks/useResults";

interface ActualResultsPanelProps {
  date: string;
}

/**
 * "Zrealizowane" — results zalogowane tego dnia obok "Zaplanowane" (adherence
 * tracking, ADR-9: prosta juxtapozycja plan vs wyniki, bez złożonej analityki w MVP).
 */
export function ActualResultsPanel({ date }: ActualResultsPanelProps) {
  const { data: results, isLoading } = useResultsByDate(date);

  if (isLoading) return <p className="text-sm text-muted-foreground">Ładowanie…</p>;

  if (!results || results.length === 0) {
    return <p className="text-sm text-muted-foreground">Brak zalogowanych wyników tego dnia.</p>;
  }

  return (
    <ul className="space-y-1.5">
      {results.map((result) => (
        <li key={result.id} className="flex items-center justify-between rounded-md border px-3 py-1.5 text-sm">
          <span>{result.metric}</span>
          <span className="tabular-nums text-muted-foreground">
            {result.value} {result.unit}
          </span>
        </li>
      ))}
    </ul>
  );
}
