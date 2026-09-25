import { AdminUsersTable } from "@/components/admin/AdminUsersTable";
import { useAdminUsers } from "@/hooks/useAdmin";
import { PAGE_SHELL_CLASS, PAGE_TITLE_CLASS } from "@/lib/layout";

/**
 * Protected by auth + `is_admin`. Budget in USD WITHOUT "Free"/"Pro" labels (ADR-16 — protective
 * budget, not a subscription plan). `max_active_personas` editable per account (ADR-12).
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
    </div>
  );
}
