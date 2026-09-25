import { useMemo, useState } from "react";
import { format } from "date-fns";
import { pl } from "date-fns/locale";
import { toast } from "sonner";
import { useGeneratePlan } from "@/hooks/usePlans";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import type { Persona, PlanPeriodType } from "@/types/api";
interface Props { open: boolean; onOpenChange: (open: boolean) => void; defaultDate: Date; personas: Persona[]; }
export function PlanGenerationDialog({ open, onOpenChange, defaultDate, personas }: Props) {
  const [step, setStep] = useState(1); const [periodType, setPeriodType] = useState<PlanPeriodType>("week"); const [startDate, setStartDate] = useState(format(defaultDate, "yyyy-MM-dd")); const [personaIds, setPersonaIds] = useState<string[]>([]); const [brief, setBrief] = useState(""); const generate = useGeneratePlan();
  const selected = useMemo(() => personaIds.length ? personaIds : personas.map((p) => p.id), [personaIds, personas]);
  function close(value: boolean) { if (!value) { setStep(1); setPersonaIds([]); setBrief(""); } onOpenChange(value); }
  async function submit() { try { await generate.mutateAsync({ period_type: periodType, start_date: startDate, persona_ids: selected, user_brief: brief.trim() || undefined }); toast.info("Rozpoczęto generowanie planu."); close(false); } catch { toast.error("Nie udało się rozpocząć generowania planu."); } }
  return <Dialog open={open} onOpenChange={close}><DialogContent className="max-w-xl"><DialogHeader><DialogTitle>Ułóż plan</DialogTitle><DialogDescription>Krok {step} z 4</DialogDescription></DialogHeader>
    {step === 1 ? <div className="space-y-4"><p className="text-sm font-medium">Na jaki okres ułożyć plan?</p><div className="grid grid-cols-3 gap-2">{(["day", "week", "month"] as PlanPeriodType[]).map((value) => <Button key={value} type="button" variant={periodType === value ? "default" : "outline"} onClick={() => setPeriodType(value)}>{value === "day" ? "Dzień" : value === "week" ? "Tydzień" : "Miesiąc"}</Button>)}</div><label className="block text-sm">Data<input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="mt-1 h-11 w-full rounded-md border bg-background px-3" /></label></div> : null}
    {step === 2 ? <div className="space-y-3"><p className="text-sm font-medium">Wybierz trenerów</p>{personas.map((persona) => { const checked = selected.includes(persona.id); return <label key={persona.id} className="flex min-h-11 items-center gap-3 rounded-md border px-3"><input type="checkbox" checked={checked} onChange={() => setPersonaIds(checked ? selected.filter((id) => id !== persona.id) : [...selected, persona.id])} />{persona.name}</label>; })}</div> : null}
    {step === 3 ? <label className="block text-sm">Dodatkowe informacje<textarea value={brief} onChange={(e) => setBrief(e.target.value)} maxLength={2000} rows={7} placeholder="Np. podróż, kontuzja, dostępny czas…" className="mt-1 w-full rounded-md border bg-background p-3" /></label> : null}
    {step === 4 ? <div className="space-y-3 text-sm"><p><strong>Okres:</strong> {periodType === "day" ? "Dzień" : periodType === "week" ? "Tydzień" : "Miesiąc"}, {format(new Date(startDate + "T12:00:00"), "d MMMM yyyy", { locale: pl })}</p><p><strong>Trenerzy:</strong> {personas.filter((p) => selected.includes(p.id)).map((p) => p.name).join(", ") || "—"}</p><label className="block"><strong>Dodatkowe informacje</strong><textarea value={brief} onChange={(e) => setBrief(e.target.value)} maxLength={2000} rows={5} className="mt-1 w-full rounded-md border bg-background p-3" /></label></div> : null}
    <DialogFooter><Button type="button" variant="outline" onClick={() => step > 1 ? setStep(step - 1) : close(false)}>Wstecz</Button>{step < 4 ? <Button type="button" onClick={() => setStep(step + 1)} disabled={step === 2 && selected.length === 0}>Dalej</Button> : <Button type="button" onClick={() => void submit()} disabled={generate.isPending || selected.length === 0}>Ułóż plan</Button>}</DialogFooter>
  </DialogContent></Dialog>;
}
