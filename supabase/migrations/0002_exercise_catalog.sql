-- Katalog ćwiczeń — ADR-14. Treść referencyjna (jak persona_templates/plan_templates),
-- seedowana migracją, bez własnego serwisu domenowego — cienki router + repozytorium.
-- Patrz docs/technical/database-schema.md, docs/technical/frontend.md (/settings).

create table public.exercises (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  name text not null,
  persona_type text not null,          -- personas.type, dla którego ćwiczenie jest widoczne w /settings
  level text not null,                 -- 'beginner' | 'intermediate' | 'advanced'
  categories text[] not null default '{}',
  short_description text not null,
  detail_full text not null,           -- "Wykonanie"
  common_mistakes text not null,       -- "Częste błędy"
  photo_path text,                     -- ścieżka w Supabase Storage (bucket publiczny 'exercise-photos'); NULL = brak zdjęcia
  created_at timestamptz not null default now(),
  constraint exercises_level_check check (level in ('beginner', 'intermediate', 'advanced')),
  constraint exercises_persona_type_check check (
    persona_type in (
      'personal_trainer', 'dietitian', 'sport_psychologist', 'psychologist',
      'motor_coach', 'badminton_coach', 'custom'
    )
  )
);

create index exercises_categories_gin_idx on public.exercises using gin (categories);
create index exercises_persona_type_idx on public.exercises (persona_type);

alter table public.exercises enable row level security;
create policy exercises_select_all on public.exercises
  for select using (true);
-- Brak INSERT/UPDATE/DELETE dla `authenticated` — treść zarządzana wyłącznie przez migracje/seed,
-- tak jak persona_templates/plan_templates. Rozbudowa o edytowalność to osobna, przyszła decyzja.

-- ============================================================
-- SEED — startowy zestaw (rozszerzać kolejnymi migracjami wraz z rozwojem katalogu)
-- ============================================================

insert into public.exercises
  (slug, name, persona_type, level, categories, short_description, detail_full, common_mistakes)
values
  ('przysiad-ze-sztanga', 'Przysiad ze sztangą', 'motor_coach', 'intermediate',
   array['Nogi'],
   'Sztanga na górnej części pleców, stopy na szerokość barków. Zejście z napiętym brzuchem, '
   || 'pięty w podłodze, aż uda równolegle do ziemi.',
   'Sztanga leży na górnej części czworobocznych, nie na karku. Stopy na szerokość barków, '
   || 'lekko rozstawione na boki. Oddech i napięcie brzucha przed zejściem. Schodź kontrolowanie, '
   || 'kolana idą w linii stóp, aż uda będą równoległe do ziemi lub niżej. Wstawanie przez '
   || 'wypchnięcie podłogi piętami, bez odrywania ich w żadnym momencie.',
   'Kolana zapadające się do środka, odrywanie pięt od podłogi, zbyt szybkie tempo zejścia bez kontroli.'),
  ('wyciskanie-sztangi-lezac', 'Wyciskanie sztangi leżąc', 'motor_coach', 'intermediate',
   array['Górna część ciała', 'Triceps'],
   'Łopatki ściągnięte i oparte na ławce, stabilne stopy na podłodze. Sztanga opada do linii '
   || 'sutków, wyprost bez odrywania miednicy.',
   'Połóż się tak, by oczy były pod sztangą. Ściągnij łopatki i oprzyj je na ławce, stopy płasko '
   || 'na podłodze dla stabilizacji. Sztanga schodzi kontrolowanie do linii sutków, łokcie pod '
   || 'kątem około 45 stopni od tułowia. Wypychanie mocne i równe obiema rękami, bez odrywania '
   || 'miednicy od ławki.',
   'Odrywanie miednicy (mostek), łokcie zbyt szeroko na boki, opuszczanie sztangi bez kontroli.'),
  ('martwy-ciag', 'Martwy ciąg', 'motor_coach', 'advanced',
   array['Nogi', 'Plecy'],
   'Sztanga blisko piszczeli, plecy neutralne. Wstawanie przez wypchnięcie podłogi nogami, '
   || 'sztanga cały czas przy ciele.',
   'Sztanga tuż przy piszczelach, stopy na szerokość bioder. Chwyt na zewnątrz nóg, plecy '
   || 'w neutralnej, lekko wygiętej pozycji — nie zaokrąglone. Wstawanie zaczyna się od wypchnięcia '
   || 'podłogi nogami, sztanga ślizga się blisko ciała przez cały ruch.',
   'Zaokrąglone plecy przy starcie, odsuwanie sztangi od nóg, przeprost w odcinku lędźwiowym na górze ruchu.'),
  ('sprint-10m', 'Sprint 10 m', 'badminton_coach', 'intermediate',
   array['Cardio / zwrotność', 'Nogi'],
   'Start wysoki, pierwsze trzy kroki krótkie i mocne. Maksymalne przyspieszenie na krótkim '
   || 'odcinku, pełny wypoczynek między seriami.',
   'Start z pozycji wysokiej, ciało lekko pochylone do przodu. Pierwsze trzy kroki krótkie '
   || 'i mocne, mocne odbicie od podłoża. Przyspieszenie maksymalne przez cały odcinek 10 metrów. '
   || 'Po każdej serii pełny wypoczynek (60 sekund) — to ćwiczenie na moc, nie na wytrzymałość.',
   'Zbyt wczesne wyprostowanie tułowia, zbyt długie pierwsze kroki, niepełny wypoczynek między seriami.'),
  ('serw-krotki-technika', 'Serw krótki — technika', 'badminton_coach', 'intermediate',
   array['Barki'],
   'Lotka uderzana blisko siatki, płaski łuk lotu. Delikatny, kontrolowany kontakt rakiety — '
   || 'nie zamach, a "pchnięcie".',
   'Lotka trzymana na wysokości pasa, rakieta z tyłu w gotowości. Ruch to krótkie "pchnięcie", '
   || 'nie zamach z dużą amplitudą. Celuj tuż za linię serwisu przeciwnika, płaski łuk lotu blisko '
   || 'górnej krawędzi siatki.',
   'Zbyt duży zamach ramieniem, uderzenie za mocne (lotka leci za daleko), niekontrolowany kontakt z lotką.');
