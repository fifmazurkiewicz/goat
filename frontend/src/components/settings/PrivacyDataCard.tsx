import { useState } from "react";
import { Download, Shield, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useGrantPrivacyConsent, usePrivacyConsent, useWithdrawPrivacyConsent } from "@/hooks/usePrivacy";
import { apiDownload, apiFetch, getErrorMessage } from "@/lib/api-client";
import { signOut as signOutSupabase } from "@/lib/supabase";
import { useAuthStore } from "@/store/useAuthStore";

export function PrivacyDataCard() {
  const { data: consent, error: consentError, isError: consentIsError, refetch: refetchConsent } = usePrivacyConsent();
  const grant = useGrantPrivacyConsent();
  const withdraw = useWithdrawPrivacyConsent();
  const signOutLocal = useAuthStore((state) => state.signOut);
  const [isExporting, setIsExporting] = useState(false);
  const [confirmation, setConfirmation] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);
  const [consentConfirmed, setConsentConfirmed] = useState(false);
  const [aiConfirmed, setAiConfirmed] = useState(false);

  async function exportData() {
    setIsExporting(true);
    try {
      const { blob, filename } = await apiDownload("/api/v1/privacy/export");
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url; anchor.download = filename; anchor.click();
      URL.revokeObjectURL(url);
      toast.success("Eksport danych został pobrany");
    } catch (error) { toast.error(getErrorMessage(error, "Nie udało się pobrać danych.")); }
    finally { setIsExporting(false); }
  }

  async function deleteAccount() {
    setIsDeleting(true);
    try {
      await apiFetch("/api/v1/privacy/account", { method: "DELETE" });
      try { await signOutSupabase(); } finally { signOutLocal(); }
      toast.success("Konto i dane zostały usunięte");
    } catch (error) { toast.error(getErrorMessage(error, "Nie udało się usunąć konta.")); setIsDeleting(false); }
  }

  return (
    <Card className="max-w-xl">
      <CardHeader><CardTitle className="flex items-center gap-2"><Shield className="h-5 w-5" />Prywatność i dane</CardTitle><CardDescription>Zarządzaj zgodą, pobierz swoje dane lub usuń konto.</CardDescription></CardHeader>
      <CardContent className="space-y-5">
        {consentIsError ? <div className="space-y-2 rounded-md border border-destructive/40 p-3 text-sm"><p className="text-destructive">{getErrorMessage(consentError, "Nie udało się wczytać stanu zgód.")}</p><Button variant="outline" onClick={() => void refetchConsent()}>Spróbuj ponownie</Button></div> : null}
        <div className="space-y-2"><p className="text-sm font-medium">Dane zdrowotne: {consent?.health_data.active ? "zgoda aktywna" : "brak zgody"}</p><p className="text-xs text-muted-foreground">Po wycofaniu zgody czat, profil, wyniki i plany będą niedostępne do czasu ponownego udzielenia zgody.</p>{consent?.health_data.active ? <Button variant="outline" disabled={withdraw.isPending} onClick={() => void withdraw.mutateAsync().catch((e) => toast.error(getErrorMessage(e, "Nie udało się wycofać zgody.")))}>Wycofaj zgodę</Button> : <><label className="flex items-start gap-2 rounded-md border p-3 text-sm"><input className="mt-1" type="checkbox" checked={consentConfirmed} onChange={(e) => setConsentConfirmed(e.target.checked)} /><span>Wyrażam dobrowolną, wyraźną zgodę na przetwarzanie danych dotyczących zdrowia w celu personalizacji coachingu.</span></label><label className="flex items-start gap-2 rounded-md border p-3 text-sm"><input className="mt-1" type="checkbox" checked={aiConfirmed} onChange={(e) => setAiConfirmed(e.target.checked)} /><span>Rozumiem użycie AI i jego ograniczenia opisane w <Link className="underline" to="/privacy">Polityce prywatności</Link>.</span></label><Button disabled={consentIsError || !consentConfirmed || !aiConfirmed || grant.isPending} onClick={() => void grant.mutateAsync().then(() => { setConsentConfirmed(false); setAiConfirmed(false); }).catch((e) => toast.error(getErrorMessage(e, "Nie udało się zapisać zgody.")))}>Udziel zgody</Button></>}</div>
        <div className="border-t pt-4"><Button variant="outline" disabled={isExporting} onClick={() => void exportData()}><Download className="mr-2 h-4 w-4" />{isExporting ? "Przygotowywanie…" : "Pobierz moje dane"}</Button></div>
        <div className="space-y-2 border-t pt-4"><p className="text-sm font-medium text-destructive">Usuń konto</p><p className="text-xs text-muted-foreground">Ta operacja trwale usuwa konto i dane aplikacji. Wpisz USUŃ, aby ją odblokować.</p><input aria-label="Potwierdzenie usunięcia konta" className="flex h-10 w-full rounded-md border bg-background px-3 py-2 text-sm" value={confirmation} onChange={(e) => setConfirmation(e.target.value)} placeholder="USUŃ" /><Button variant="destructive" disabled={confirmation !== "USUŃ" || isDeleting} onClick={() => void deleteAccount()}><Trash2 className="mr-2 h-4 w-4" />{isDeleting ? "Usuwanie…" : "Usuń konto i dane"}</Button></div>
        <p className="border-t pt-4 text-sm"><Link className="underline" to="/privacy">Polityka prywatności</Link><span aria-hidden> · </span><Link className="underline" to="/terms">Warunki korzystania</Link><span aria-hidden> · </span><a className="underline" href="mailto:fmazurkiewicz@gmail.com">Kontakt</a></p>
      </CardContent>
    </Card>
  );
}
