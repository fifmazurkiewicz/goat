import { NavLink, Outlet } from "react-router-dom";

import { cn } from "@/lib/utils";
import { usePlanGenerationStore } from "@/store/usePlanGenerationStore";

const NAV_ITEMS = [
  { to: "/personas", label: "Persony" },
  { to: "/chat", label: "Czat" },
  { to: "/plans", label: "Plany" },
  { to: "/results", label: "Wyniki" },
  { to: "/profile", label: "Profil" },
];

/**
 * App shell / root layout dla tras chronionych. `usePlanGenerationStore` jest
 * odczytywany tutaj (nie w /plans) zgodnie z docs/technical/frontend.md
 * sekcja 2 — docelowo tu też będzie żył polling `GET /plans/jobs/{id}` i
 * side-effect toastów przy zmianie statusu (kolejny etap).
 */
export function AppShell() {
  const planStatus = usePlanGenerationStore((state) => state.status);

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="container flex h-14 items-center justify-between">
          <span className="font-semibold">Coach</span>
          <nav className="flex gap-4 text-sm">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    "text-muted-foreground transition-colors hover:text-foreground",
                    isActive && "font-medium text-foreground"
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      {planStatus === "generating" && (
        <div className="border-b bg-muted/50 py-2 text-center text-sm text-muted-foreground">
          Generowanie planu w toku…
        </div>
      )}
      <main>
        <Outlet />
      </main>
    </div>
  );
}
