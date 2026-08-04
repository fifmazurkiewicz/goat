-- Metryki biegowe pod category=strength (trener motoryczny / kondycja).
-- Bez osobnej kategorii „running” — FE mapuje motor_coach → strength („Trening”).

insert into public.allowed_metrics (category, metric_key, unit, value_type, value_min, value_max)
values
  ('strength', 'run_distance_km', 'km', 'numeric', 0, 100),
  ('strength', 'run_time_min', 'min', 'numeric', 0, 600),
  ('strength', 'run_pace_min_per_km', 'min/km', 'numeric', 2, 15)
on conflict (category, metric_key) do nothing;
