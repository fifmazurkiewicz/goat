import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useUpdateUserProfile, useUserProfile } from "@/hooks/useUserProfile";
import { getErrorMessage } from "@/lib/api-client";
import {
  ACTIVITY_LEVEL_LABELS,
  CRITICAL_PROFILE_FIELD_LABELS,
  PRIMARY_GOAL_LABELS,
  SEX_LABELS,
} from "@/lib/user-profile-labels";
import type { ActivityLevel, PrimaryGoal, Sex, UserProfileUpdate } from "@/types/api";

const NONE = "__none__";

type FormState = {
  height_cm: string;
  weight_kg: string;
  date_of_birth: string;
  sex: Sex | null;
  activity_level: ActivityLevel | null;
  primary_goal: PrimaryGoal | null;
  notes: string;
};

const EMPTY_FORM: FormState = {
  height_cm: "",
  weight_kg: "",
  date_of_birth: "",
  sex: null,
  activity_level: null,
  primary_goal: null,
  notes: "",
};

function profileToForm(profile: ReturnType<typeof useUserProfile>["data"]): FormState {
  if (!profile) return { ...EMPTY_FORM };
  return {
    height_cm: profile.height_cm != null ? String(profile.height_cm) : "",
    weight_kg: profile.weight_kg != null ? String(profile.weight_kg) : "",
    date_of_birth: profile.date_of_birth ?? "",
    sex: profile.sex,
    activity_level: profile.activity_level,
    primary_goal: profile.primary_goal,
    notes: profile.notes ?? "",
  };
}

function parseOptionalNumber(raw: string): number | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  const value = Number(trimmed.replace(",", "."));
  return Number.isFinite(value) ? value : null;
}

function buildPatch(saved: FormState, current: FormState): UserProfileUpdate | null {
  const patch: UserProfileUpdate = {};

  const height = parseOptionalNumber(current.height_cm);
  const savedHeight = parseOptionalNumber(saved.height_cm);
  if (height !== savedHeight) patch.height_cm = height;

  const weight = parseOptionalNumber(current.weight_kg);
  const savedWeight = parseOptionalNumber(saved.weight_kg);
  if (weight !== savedWeight) patch.weight_kg = weight;

  const dob = current.date_of_birth.trim() || null;
  const savedDob = saved.date_of_birth.trim() || null;
  if (dob !== savedDob) patch.date_of_birth = dob;

  if (current.sex !== saved.sex) patch.sex = current.sex;
  if (current.activity_level !== saved.activity_level) patch.activity_level = current.activity_level;
  if (current.primary_goal !== saved.primary_goal) patch.primary_goal = current.primary_goal;

  const notes = current.notes.trim() || null;
  const savedNotes = saved.notes.trim() || null;
  if (notes !== savedNotes) patch.notes = notes;

  return Object.keys(patch).length > 0 ? patch : null;
}

function missingCriticalFields(form: FormState): string[] {
  const missing: string[] = [];
  if (!form.height_cm.trim()) missing.push(CRITICAL_PROFILE_FIELD_LABELS.height_cm);
  if (!form.weight_kg.trim()) missing.push(CRITICAL_PROFILE_FIELD_LABELS.weight_kg);
  if (!form.date_of_birth.trim()) missing.push(CRITICAL_PROFILE_FIELD_LABELS.date_of_birth);
  if (!form.activity_level) missing.push(CRITICAL_PROFILE_FIELD_LABELS.activity_level);
  if (!form.primary_goal) missing.push(CRITICAL_PROFILE_FIELD_LABELS.primary_goal);
  return missing;
}

function formatUpdatedAt(iso: string | undefined): string | null {
  if (!iso) return null;
  try {
    return new Intl.DateTimeFormat("pl-PL", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(iso));
  } catch {
    return null;
  }
}

/**
 * Formularz `user_profile` (ADR-11) — ta sama tabela co tool `update_user_profile` w czacie.
 */
export function UserProfileForm() {
  const { data: profile, isLoading } = useUserProfile();
  const updateProfile = useUpdateUserProfile();

  const [savedForm, setSavedForm] = useState<FormState>(EMPTY_FORM);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [syncedUpdatedAt, setSyncedUpdatedAt] = useState<string | null>(null);

  useEffect(() => {
    if (isLoading) return;
    const next = profileToForm(profile);
    const profileStamp = profile?.updated_at ?? "__empty__";
    if (syncedUpdatedAt !== profileStamp) {
      setSavedForm(next);
      setForm(next);
      setSyncedUpdatedAt(profileStamp);
    }
  }, [profile, isLoading, syncedUpdatedAt]);

  const patch = useMemo(() => buildPatch(savedForm, form), [savedForm, form]);
  const isDirty = patch !== null;
  const missing = useMemo(() => missingCriticalFields(form), [form]);
  const updatedLabel = formatUpdatedAt(profile?.updated_at);

  async function handleSave() {
    if (!patch) return;
    try {
      await updateProfile.mutateAsync(patch);
      toast.success("Zapisano profil");
    } catch (err) {
      toast.error(getErrorMessage(err, "Nie udało się zapisać profilu"));
    }
  }

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Ładowanie profilu…</p>;
  }

  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle>Twoje dane coachingowe</CardTitle>
        <CardDescription>
          Wspólna pamięć dla Goat i wszystkich person — waga, cele, notatki. Trenerzy mogą uzupełniać
          te informacje w czacie; tutaj możesz je też zobaczyć i poprawić ręcznie.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {missing.length > 0 ? (
          <p className="rounded-md border border-dashed px-3 py-2 text-sm text-muted-foreground">
            Brakuje jeszcze: {missing.join(", ")}. Persony mogą dopytać o to w rozmowie albo uzupełnij
            poniżej.
          </p>
        ) : (
          <p className="text-sm text-muted-foreground">Profil kompletny — trenerzy mają kluczowe dane do personalizacji.</p>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="height_cm">Wzrost (cm)</Label>
            <Input
              id="height_cm"
              inputMode="decimal"
              placeholder="np. 178"
              value={form.height_cm}
              onChange={(e) => setForm((prev) => ({ ...prev, height_cm: e.target.value }))}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="weight_kg">Waga (kg)</Label>
            <Input
              id="weight_kg"
              inputMode="decimal"
              placeholder="np. 75"
              value={form.weight_kg}
              onChange={(e) => setForm((prev) => ({ ...prev, weight_kg: e.target.value }))}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="date_of_birth">Data urodzenia</Label>
            <Input
              id="date_of_birth"
              type="date"
              value={form.date_of_birth}
              onChange={(e) => setForm((prev) => ({ ...prev, date_of_birth: e.target.value }))}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="sex">Płeć</Label>
            <Select
              value={form.sex ?? NONE}
              onValueChange={(value) =>
                setForm((prev) => ({ ...prev, sex: value === NONE ? null : (value as Sex) }))
              }
            >
              <SelectTrigger id="sex">
                <SelectValue placeholder="Wybierz" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>Nie podano</SelectItem>
                {(Object.entries(SEX_LABELS) as [Sex, string][]).map(([key, label]) => (
                  <SelectItem key={key} value={key}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="activity_level">Poziom aktywności</Label>
            <Select
              value={form.activity_level ?? NONE}
              onValueChange={(value) =>
                setForm((prev) => ({
                  ...prev,
                  activity_level: value === NONE ? null : (value as ActivityLevel),
                }))
              }
            >
              <SelectTrigger id="activity_level">
                <SelectValue placeholder="Wybierz" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>Nie podano</SelectItem>
                {(Object.entries(ACTIVITY_LEVEL_LABELS) as [ActivityLevel, string][]).map(
                  ([key, label]) => (
                    <SelectItem key={key} value={key}>
                      {label}
                    </SelectItem>
                  )
                )}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="primary_goal">Główny cel</Label>
            <Select
              value={form.primary_goal ?? NONE}
              onValueChange={(value) =>
                setForm((prev) => ({
                  ...prev,
                  primary_goal: value === NONE ? null : (value as PrimaryGoal),
                }))
              }
            >
              <SelectTrigger id="primary_goal">
                <SelectValue placeholder="Wybierz" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>Nie podano</SelectItem>
                {(Object.entries(PRIMARY_GOAL_LABELS) as [PrimaryGoal, string][]).map(
                  ([key, label]) => (
                    <SelectItem key={key} value={key}>
                      {label}
                    </SelectItem>
                  )
                )}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="notes">Notatki</Label>
            <Textarea
              id="notes"
              rows={4}
              maxLength={1000}
              placeholder="Kontuzje, preferencje, ograniczenia dietetyczne — wszystko, co trenerzy powinni pamiętać."
              value={form.notes}
              onChange={(e) => setForm((prev) => ({ ...prev, notes: e.target.value }))}
            />
            <p className="text-xs text-muted-foreground">{form.notes.length}/1000 znaków</p>
          </div>
        </div>

        <div className="sticky bottom-0 z-10 mt-4 flex flex-wrap items-center justify-between gap-3 border-t bg-card pt-3 pb-[max(0.25rem,env(safe-area-inset-bottom))]">
          <div className="text-xs text-muted-foreground">
            {updatedLabel ? `Ostatnia aktualizacja: ${updatedLabel}` : "Profil jeszcze nie zapisany"}
          </div>
          <Button type="button" className="min-h-11" onClick={() => void handleSave()} disabled={!isDirty || updateProfile.isPending}>
            {updateProfile.isPending ? "Zapisywanie…" : "Zapisz profil"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
