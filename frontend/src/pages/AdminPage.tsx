import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { DeployVersionPanel } from "@/components/admin/DeployVersionPanel";
import { AdminUsersTable } from "@/components/admin/AdminUsersTable";
import { AuditLogPanel } from "@/components/admin/AuditLogPanel";
import { ModerationEventsPanel } from "@/components/admin/ModerationEventsPanel";
import { useAdminUsers } from "@/hooks/useAdmin";
import { PAGE_SHELL_CLASS, PAGE_TITLE_CLASS } from "@/lib/layout";

/**
 * Chroniona auth + `is_admin`. Kwota w USD BEZ etykiet "Free"/"Pro" (ADR-16 — budżet
 * ochronny, nie plan subskrypcyjny). `max_active_personas` edytowalne per konto (ADR-12).
 */
export default function AdminPage() {
  const { data: users, isLoading } = useAdminUsers();

  return (
    <div className={PAGE_SHELL_CLASS}>
      <h1 className={PAGE_TITLE_CLASS}>Panel admina</h1>
      <p className="mt-2 max-w-[70ch] text-muted-foreground">
        Konta, budżety i limity person. Diagnostyka platformy (moderacja, log audytowy) jest opcjonalna —
        przydatna głównie przy incydentach bezpieczeństwa lub wielu użytkownikach.
      </p>

      <DeployVersionPanel />

      <section className="mt-6">
        <h2 className="text-lg font-medium">Użytkownicy</h2>
        <div className="mt-4">
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Ładowanie…</p>
          ) : (
            <AdminUsersTable users={users ?? []} />
          )}
        </div>
      </section>

      <Accordion type="single" collapsible className="mt-8 w-full max-w-4xl">
        <AccordionItem value="diagnostics">
          <AccordionTrigger className="text-sm text-muted-foreground">
            Diagnostyka platformy (moderacja, log audytowy)
          </AccordionTrigger>
          <AccordionContent className="space-y-8 pt-2">
            <section>
              <h3 className="text-base font-medium">Moderacja</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Próby jailbreaku i naruszenia zasad person — log techniczny, nie dotyczy zwykłego czatu.
              </p>
              <div className="mt-4">
                <ModerationEventsPanel />
              </div>
            </section>
            <section>
              <h3 className="text-base font-medium">Log audytowy</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Historia akcji admina (reset hasła, zmiana limitów/budżetu).
              </p>
              <div className="mt-4">
                <AuditLogPanel />
              </div>
            </section>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  );
}
