import type { ActivityLevel, PrimaryGoal, Sex } from "@/types/api";

export const SEX_LABELS: Record<Sex, string> = {
  male: "Mężczyzna",
  female: "Kobieta",
  other: "Inna",
};

export const ACTIVITY_LEVEL_LABELS: Record<ActivityLevel, string> = {
  sedentary: "Siedzący tryb życia",
  light: "Lekka aktywność",
  moderate: "Umiarkowana aktywność",
  active: "Aktywny",
  very_active: "Bardzo aktywny",
};

export const PRIMARY_GOAL_LABELS: Record<PrimaryGoal, string> = {
  lose_weight: "Redukcja wagi",
  build_muscle: "Budowa masy mięśniowej",
  improve_endurance: "Poprawa wytrzymałości",
  general_health: "Ogólne zdrowie",
  sport_specific: "Cel specyficzny dla dyscypliny",
};

export const CRITICAL_PROFILE_FIELD_LABELS: Record<string, string> = {
  height_cm: "wzrost",
  weight_kg: "waga",
  date_of_birth: "data urodzenia",
  activity_level: "poziom aktywności",
  primary_goal: "główny cel",
};
