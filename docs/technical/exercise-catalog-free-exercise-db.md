# Import katalogu ćwiczeń z `free-exercise-db` — założenia (draft do wdrożenia w Cursorze)

Status: **draft, nieskonsultowany z ADR** — do przejrzenia przed implementacją. Nie zawiera kodu,
tylko decyzje projektowe i mapowanie pól.

## 1. Cel

Rozszerzyć katalog ćwiczeń (ADR-14, `docs/technical/frontend.md` sekcja "Katalog ćwiczeń") o miniaturki
zdjęciowe i szerszy zestaw pozycji, bez ryzyka licencyjnego — zamiast datasetu hasaneyldrm/exercises-dataset
(media © Gym visual, płatna licencja poza 4 darmowymi animacjami), źródłem jest
[`yuhonas/free-exercise-db`](https://github.com/yuhonas/free-exercise-db) (fork projektu `wrkout/exercises.json`).

## 2. Źródło i licencja

- Repo: `github.com/yuhonas/free-exercise-db`, dane: `dist/exercises.json`, obrazy: `exercises/<Id>/0.jpg`, `1.jpg`.
- Licencja: **Unlicense** (domena publiczna) — bez ograniczeń komercyjnych, **bez wymogu atrybucji**
  (w przeciwieństwie do poprzedniego pomysłu z Gym visual).
- ~800+ ćwiczeń, każde z 1–2 statycznymi zdjęciami JPG (pozycja startowa/końcowa) — **nie GIF-y/wideo**.
  To świadomy kompromis: zero ryzyka prawnego i zero kosztu, kosztem braku animacji.
- Warto zapisać link źródłowy w komentarzu SQL/README (nie jako wymóg prawny, tylko dla przyszłego "skąd to się wzięło").

## 3. Zakres importu

- Import **jednorazowy, offline** (skrypt, nie runtime fetch) — dane trafiają do migracji/seeda, tak jak dziś
  ręcznie pisane ćwiczenia w `0002_exercise_catalog.sql`.
- Import obejmuje **całość** datasetu (~800 pozycji) — filtrowanie/kuracja tylko tam, gdzie brak obrazów
  (pomiń rekordy bez `images`) lub gdzie `name`/`instructions` są puste.
- **Nie obejmuje** ćwiczeń specyficznych dla badmintona (`badminton_coach`) — dataset to ogólny katalog
  siłowni/cardio, bez dryli sportowych. Istniejące ręczne wpisy `badminton_coach` (`sprint-10m`,
  `serw-krotki-technika`) zostają nietknięte.

## 4. Mapowanie pól źródło → `exercises`

| `exercises` (obecna kolumna) | Źródło w free-exercise-db | Uwaga |
|---|---|---|
| `slug` | `id` (np. `Barbell_Squat`) → slugify | dedup po slug, `on conflict do nothing` |
| `name` | `name` | **zostaje po angielsku** (patrz sekcja 7) |
| `persona_type` | stała `'motor_coach'` dla wszystkich importowanych | dataset nie ma podziału na persony |
| `level` | `level` (`beginner`/`intermediate`/`expert`) | `expert` → `advanced` (mapowanie 1:1 poza tym) |
| `categories` | `primaryMuscles` + `category` | translacja słownikowa PL (mała, stała lista ~20 nazw mięśni + ~7 kategorii typu `strength`/`cardio`/`stretching`) |
| `short_description` | pierwsze zdanie/krok z `instructions[0]` | brak osobnego pola "teaser" w źródle |
| `detail_full` | `instructions` (array) połączone w listę numerowaną | zostaje po angielsku |
| `common_mistakes` | **brak w źródle** | patrz sekcja 5 — wymaga zmiany constraintu |
| `photo_path` | `images[0]` (pełny URL po uploadzie) | patrz sekcja 6 |

Pola źródła bez odpowiednika w schemacie (`equipment`, `force`, `mechanic`, `secondaryMuscles`) — **pomijamy
w v1**, nie dodajemy nowych kolumn, żeby nie rozjeżdżać zakresu. Do rozważenia później, jeśli okaże się
przydatne w czacie person.

## 5. Zmiana schematu (nowa migracja `0012_exercise_catalog_free_exercise_db.sql`)

Obecny constraint: `common_mistakes text not null`. Dataset źródłowy nie ma pola "częste błędy" — **nie
wolno tego zmyślać/generować sztucznie** dla 800 pozycji (ryzyko błędnych porad technicznych bez weryfikacji).

Decyzja: `alter table exercises alter column common_mistakes drop not null;` — importowane rekordy mają
`common_mistakes = NULL`; ręcznie pisane (obecne 5) zostają bez zmian (mają wartość).

Dodatkowo:
- `alter table exercises add column source text not null default 'manual';` z constraintem
  `check (source in ('manual', 'free_exercise_db'))` — **żeby przyszły import nigdy nie nadpisał ręcznie
  kuratorowanych wpisów** i żeby UI mogło (opcjonalnie) rozróżnić jakość treści.
- Import robimy jako `insert ... on conflict (slug) do nothing` — idempotentny, bezpieczny do ponownego uruchomienia.

## 6. Media — hosting obrazów

**Rekomendacja: self-host w Supabase Storage**, bucket `exercise-photos` (już wspomniany w komentarzu
`0002_exercise_catalog.sql` jako plan), zamiast hotlinkować `raw.githubusercontent.com`:
- niezależność od dostępności/rate-limitów GitHuba w produkcji,
- `photo_path` w obecnym kodzie (`ExerciseGrid.tsx`, `ExerciseDetailDialog.tsx`) jest już renderowany
  bezpośrednio jako `<img src={exercise.photo_path}>` — czyli to pełny URL, nie ścieżka względna; zmiana
  źródła jest transparentna dla frontendu, **zero zmian w komponentach** poza obsługą `common_mistakes === null`.
- Rozmiar: ~800 ćwiczeń × ~2 zdjęcia × kilkadziesiąt KB = raczej pojedyncze dziesiątki MB, bez porównania
  z 140 MB z poprzedniego pomysłu (hasaneyldrm) — wygodnie mieści się w darmowym tierze Supabase Storage.

Skrypt importu: pobiera `dist/exercises.json` + folder `exercises/`, wybiera pierwsze zdjęcie na ćwiczenie,
wrzuca do bucketu, zapisuje publiczny URL jako `photo_path`.

## 7. Język — otwarta decyzja, domyślnie: zostawiamy angielski

Dataset jest **wyłącznie po angielsku** (w przeciwieństwie do hasaneyldrm, który miał polski). Dwie opcje:

- **(domyślna, v1)** `name`/`detail_full` zostają po angielsku dla importowanych ~800 pozycji;
  tłumaczymy tylko małe, stałe słowniki: nazwy kategorii (`categories`) i etykiety poziomu (już są PL
  w `LEVEL_LABELS`). Tanie, bez ryzyka błędu tłumaczenia maszynowego w instrukcji technicznej ćwiczenia.
- **(v2, opcjonalnie później)** Batch-tłumaczenie `name`+`detail_full` przez istniejącą integrację
  OpenRouter (jednorazowy skrypt offline, nie runtime) — wymaga ręcznej weryfikacji próbki wyników,
  bo błędne tłumaczenie instrukcji technicznej (np. kolejność ruchu) jest gorsze niż zostawienie EN.

Rekomenduję zacząć od wariantu v1 i ocenić, czy angielskie nazwy przeszkadzają w praktyce (persony i tak
komunikują się z userem po polsku we własnych opisach — katalog to głównie materiał poglądowy/referencyjny).

## 8. UI — zmiany minimalne

- `ExerciseDetailDialog.tsx`: sekcja "Częste błędy" renderowana warunkowo — ukryta, gdy `common_mistakes === null`
  (zamiast zawsze pokazywać pusty/sztuczny tekst).
- `ExerciseCatalog.tsx`/`useExercises.ts`: bez zmian w logice filtrowania — działa na tych samych polach.
- **Do sprawdzenia przy implementacji:** obecny `ExerciseCatalog` ładuje wszystkie ćwiczenia do pamięci i
  renderuje pełną siatkę po stronie klienta (`docs/technical/frontend.md` sekcja 7a — świadoma decyzja dla
  małego katalogu). Przy skoku z ~5 do ~800 pozycji **to założenie może przestać się skalować** (800 kart ze
  zdjęciami w DOM) — do oceny w Cursorze, czy potrzeba paginacji/lazy-loadingu, czy grid z `line-clamp` i
  `loading="lazy"` na `<img>` wystarczy.

## 9. Poza zakresem tego draftu

- Animacje/GIF-y — świadomie odpuszczone (patrz analiza wcześniej: brak w pełni darmowego źródła na tę skalę).
- `equipment`, `force`, `mechanic`, `secondaryMuscles` — nowe kolumny, nie teraz.
- Tłumaczenie pełnej treści na PL (v2, opisane w sekcji 7).
- Ćwiczenia dla `badminton_coach` — dataset ich nie pokrywa, zostają jak są.

## 10. Kolejność wdrożenia (dla Cursora)

1. Migracja `0012_exercise_catalog_free_exercise_db.sql`: `source` column + `common_mistakes` nullable.
2. Skrypt importu (jednorazowy, np. `scripts/import_free_exercise_db.py`): pobranie JSON, mapowanie wg
   sekcji 4, upload obrazów do Supabase Storage, `INSERT ... ON CONFLICT (slug) DO NOTHING`.
3. Mały słownik tłumaczeń kategorii/mięśni PL (stała mapa w skrypcie, nie w kodzie produkcyjnym backendu).
4. Zmiana w `ExerciseDetailDialog.tsx` — warunkowe renderowanie "Częste błędy".
5. Uruchomienie importu lokalnie → weryfikacja wizualna w `/settings` katalogu ćwiczeń → dopiero potem
   migracja na cloud Supabase (zgodnie z Twoim flow: SQL Editor, re-init przez `reset_public.sql` → kolejne migracje).
