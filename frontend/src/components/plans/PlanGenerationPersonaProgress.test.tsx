import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { PlanGenerationPersonaProgress } from "@/components/plans/PlanGenerationPersonaProgress";
import { TEAM_LEAD_DISPLAY_LABEL } from "@/lib/team-lead";
import type { Persona, PlanGenerationJobPersonaBreakdown, PlanItem } from "@/types/api";

const personas: Persona[] = [
  {
    id: "p1",
    user_id: "u1",
    name: "Dietetyk",
    slug: "dietetyk",
    type: "dietitian",
    system_prompt: "x",
    base_template_id: null,
    plan_template_id: null,
    template_overrides: null,
    detail_level: "simple",
    custom_result_category: null,
    is_shared: false,
    moderation_status: "approved",
    cloned_from_persona_id: null,
    active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

const breakdownDone: PlanGenerationJobPersonaBreakdown[] = [
  { persona_id: "p1", status: "done", retry_count: 0, last_error: null },
];

describe("PlanGenerationPersonaProgress", () => {
  it("shows Goat · Kierownik while harmonizing", () => {
    render(
      <PlanGenerationPersonaProgress
        breakdown={breakdownDone}
        personas={personas}
        planItems={[] as PlanItem[]}
        jobStatus="generating"
      />
    );
    expect(screen.getByText(TEAM_LEAD_DISPLAY_LABEL)).toBeInTheDocument();
    expect(screen.getByText(/harmonizuje/i)).toBeInTheDocument();
    expect(screen.queryByText(/Harmonizacja planu/i)).not.toBeInTheDocument();
  });

  it("after ready, marks Goat as Done", () => {
    render(
      <PlanGenerationPersonaProgress
        breakdown={breakdownDone}
        personas={personas}
        planItems={[] as PlanItem[]}
        jobStatus="ready"
      />
    );
    expect(screen.getByText(TEAM_LEAD_DISPLAY_LABEL)).toBeInTheDocument();
    const labels = screen.getAllByText("Gotowe");
    expect(labels.length).toBeGreaterThanOrEqual(1);
  });
});
