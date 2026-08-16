import { useState } from "react";
import { Check, Pencil, Trash2, X } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useDeleteResult, useUpdateResult } from "@/hooks/useResults";
import { getErrorMessage } from "@/lib/api-client";
import type { Result, ResultCategory } from "@/types/api";

interface ResultsTableProps {
  results: Result[];
  category: ResultCategory;
}

/**
 * Tabela z edycją inline i dodawaniem ręcznym (docs/technical/frontend.md sekcja 6).
 * Pierwsza kolumna `sticky left-0` + poziomy scroll (sekcja 11 — dane tabelaryczne
 * czytelniejsze jako tabela nawet przy scrollu, w odróżnieniu od `PlanItemTable`).
 */
export function ResultsTable({ results, category }: ResultsTableProps) {
  const updateResult = useUpdateResult(category);
  const deleteResult = useDeleteResult(category);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<{ value: string; unit: string; notes: string }>({
    value: "",
    unit: "",
    notes: "",
  });

  function startEdit(result: Result) {
    setEditingId(result.id);
    setDraft({ value: String(result.value), unit: result.unit, notes: result.notes ?? "" });
  }

  async function saveEdit(id: string) {
    try {
      await updateResult.mutateAsync({
        id,
        input: { value: Number(draft.value), unit: draft.unit, notes: draft.notes || null },
      });
      setEditingId(null);
    } catch (err) {
      toast.error(getErrorMessage(err, "Nie udało się zapisać zmian."));
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteResult.mutateAsync(id);
    } catch (err) {
      toast.error(getErrorMessage(err, "Nie udało się usunąć wpisu."));
    }
  }

  const sorted = [...results].sort((a, b) => b.logged_date.localeCompare(a.logged_date));

  return (
    <div className="overflow-x-auto rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="sticky left-0 bg-background">Data</TableHead>
            <TableHead>Metryka</TableHead>
            <TableHead>Wartość</TableHead>
            <TableHead>Jedn.</TableHead>
            <TableHead>Źródło</TableHead>
            <TableHead>Notatki</TableHead>
            <TableHead className="text-right">Akcje</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((result) => {
            const isEditing = editingId === result.id;
            return (
              <TableRow key={result.id}>
                <TableCell className="sticky left-0 bg-background text-muted-foreground">
                  {result.logged_date}
                </TableCell>
                <TableCell>{result.metric}</TableCell>
                <TableCell className="tabular-nums">
                  {isEditing ? (
                    <Input
                      className="h-8 w-24"
                      type="number"
                      value={draft.value}
                      onChange={(e) => setDraft((d) => ({ ...d, value: e.target.value }))}
                    />
                  ) : (
                    result.value
                  )}
                </TableCell>
                <TableCell>
                  {isEditing ? (
                    <Input
                      className="h-8 w-16"
                      value={draft.unit}
                      onChange={(e) => setDraft((d) => ({ ...d, unit: e.target.value }))}
                    />
                  ) : (
                    result.unit
                  )}
                </TableCell>
                <TableCell>
                  <Badge variant={result.source === "agent" ? "default" : "secondary"}>
                    {result.source === "agent" ? "Agent" : "Ręczny wpis"}
                  </Badge>
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {isEditing ? (
                    <Input
                      className="h-8"
                      value={draft.notes}
                      onChange={(e) => setDraft((d) => ({ ...d, notes: e.target.value }))}
                    />
                  ) : (
                    result.notes ?? "—"
                  )}
                </TableCell>
                <TableCell className="text-right">
                  {isEditing ? (
                    <div className="flex justify-end gap-1">
                      <Button size="icon" variant="ghost" className="min-h-11 min-w-11" onClick={() => saveEdit(result.id)} aria-label="Zapisz">
                        <Check className="h-4 w-4" />
                      </Button>
                      <Button size="icon" variant="ghost" className="min-h-11 min-w-11" onClick={() => setEditingId(null)} aria-label="Anuluj">
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  ) : (
                    <div className="flex justify-end gap-1">
                      <Button size="icon" variant="ghost" className="min-h-11 min-w-11" onClick={() => startEdit(result)} aria-label="Edytuj">
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button size="icon" variant="ghost" className="min-h-11 min-w-11" onClick={() => handleDelete(result.id)} aria-label="Usuń">
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  )}
                </TableCell>
              </TableRow>
            );
          })}
          {sorted.length === 0 ? (
            <TableRow>
              <TableCell colSpan={7} className="text-center text-muted-foreground">
                Brak wyników w tej kategorii.
              </TableCell>
            </TableRow>
          ) : null}
        </TableBody>
      </Table>
    </div>
  );
}
