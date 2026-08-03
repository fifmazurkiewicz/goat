import { AdminUsersTable } from "@/components/admin/AdminUsersTable";
import { AuditLogPanel } from "@/components/admin/AuditLogPanel";
import { ModerationEventsPanel } from "@/components/admin/ModerationEventsPanel";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAdminUsers } from "@/hooks/useAdmin";

/**
 * Chroniona auth + `is_admin`. Kwota w USD BEZ etykiet "Free"/"Pro" (ADR-16 — budżet
 * ochronny, nie plan subskrypcyjny). `max_active_personas` edytowalne per konto (ADR-12).
 */
export default function AdminPage() {
  const { data: users, isLoading } = useAdminUsers();

  return (
    <div className="container py-10">
      <h1 className="text-3xl font-semibold tracking-tight">Panel admina</h1>
      <p className="mt-2 max-w-[70ch] text-muted-foreground">
        Przegląd kont, budżetów, limitów person, zdarzeń moderacji i logu audytowego akcji administracyjnych.
      </p>

      <Tabs defaultValue="users" className="mt-6">
        <TabsList>
          <TabsTrigger value="users">Użytkownicy</TabsTrigger>
          <TabsTrigger value="moderation">Moderacja</TabsTrigger>
          <TabsTrigger value="audit">Log audytowy</TabsTrigger>
        </TabsList>
        <TabsContent value="users" className="mt-4">
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Ładowanie…</p>
          ) : (
            <AdminUsersTable users={users ?? []} />
          )}
        </TabsContent>
        <TabsContent value="moderation" className="mt-4">
          <ModerationEventsPanel />
        </TabsContent>
        <TabsContent value="audit" className="mt-4">
          <AuditLogPanel />
        </TabsContent>
      </Tabs>
    </div>
  );
}
