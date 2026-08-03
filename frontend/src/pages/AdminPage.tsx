import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * Chroniona auth + is_admin (docs/technical/database-schema.md —
 * profiles.is_admin, admin_audit_log, moderation_events). TODO: kolejny etap
 * — panel przeglądu moderation_events i akcji admina (z audit logiem).
 *
 * Lista userów (`GET /admin/users`) ma zawierać edytowalne pole
 * `max_active_personas` per konto (ADR-12, `PATCH /admin/users/{id}/persona-limit`) —
 * zastępuje dotychczasową globalną stałą "5 aktywnych person".
 */
export default function AdminPage() {
  return (
    <div className="container py-10">
      <Card>
        <CardHeader>
          <CardTitle>Panel admina</CardTitle>
          <CardDescription>
            Tu pojawi się przegląd zdarzeń moderacji i akcje administracyjne (reset limitów,
            przegląd userów, limit aktywnych person per konto) z logiem audytowym.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">TODO: kolejny etap.</CardContent>
      </Card>
    </div>
  );
}
