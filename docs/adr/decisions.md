# Log decyzji architektonicznych (ADR)

## ADR-1: Generowanie planu — bez osobnego workera na Render

**Status:** zaakceptowane (potwierdzone przez użytkownika).

**Kontekst:** generowanie planu tygodnia/miesiąca to potencjalnie długo trwająca operacja (dziesiątki sekund do kilku minut). Render nie ma darmowego tieru dla Background Workers (min. Starter $7/mies.).

**Decyzja:** wykonanie w tym samym procesie co API (`BackgroundTasks` FastAPI), opakowane w trwałe tabele `plan_generation_jobs`/`plan_generation_job_personas` (nie tylko kolumna `plans.status`) — daje widoczność, retry per-persona i partial-success bez kosztu drugiego serwisu.

**Konsekwencje:** wymaga reapera przy starcie aplikacji (zawieszone joby po restarcie → `error`) i pilnowania, żeby ciężkie/blokujące operacje nie zamrażały aktywnych streamów SSE w tym samym procesie (`asyncio.to_thread` dla sync fragmentów).

**Próg migracji:** gdy czas generowania zacznie zbliżać się do kilkunastu minut albo obciążenie RAM/CPU zacznie wpływać na responsywność czatu → wydzielić osobny Render Background Worker konsumujący tę samą tabelę `jobs` jako kolejkę (`SELECT ... FOR UPDATE SKIP LOCKED`). Schemat bazy już to wspiera bez zmian.

---

## ADR-2: Generowanie planu — trzy etapy, priorytet: synchronizacja między personami

**Status:** zaakceptowane.

**Kontekst:** pojedynczy mega-prompt ze wszystkimi personami naraz ryzykuje ucięcie JSON (20-45k tokenów output przy 5 personach/miesiąc) i "rozmycie" jakości dla dalszych person w kolejce. Jednocześnie priorytetem produktowym jest spójność planu między personami (dieta pod trening, regeneracja), nie tylko jakość pojedynczej persony w izolacji.

**Decyzja:** pipeline 3-etapowy — (1) coordinator pass (tani model, wspólny szkielet), (2) per-persona generacja równoległa (`PLANNER_MODEL`, `asyncio.gather`), (3) harmonizacja ("zarządca kalendarza" — przegląd całości, targeted patche dla konfliktów).

**Konsekwencje:** dodatkowe wywołanie LLM (etap 3) zwiększa koszt generacji o ok. jedno wywołanie plannera, ale adresuje wymóg synchronizacji explicite, zamiast liczyć na to, że model sam to zapewni w izolowanych wywołaniach per-persona.

---

## ADR-3: RLS jako rzeczywista bariera — backend łączy się jako authenticated user

**Status:** zaakceptowane.

**Kontekst:** backend połączony domyślnie przez `service_role` unieważniłby RLS jako mechanizm ochrony — każdy bug w kodzie stałby się potencjalnym wyciekiem danych między userami.

**Decyzja:** backend łączy się per-request jako authenticated user (`SET LOCAL` + `set_config('request.jwt.claims', ...)` z JWT, w ramach jednej transakcji). `service_role` wyłącznie do Supabase Admin API i `/admin/*`, z jawną kodową weryfikacją `profiles.is_admin`.

**Konsekwencje:** wymaga `NullPool` + `statement_cache_size=0` w `asyncpg` (kompatybilność z Supavisor transaction mode) i obowiązkowego testu kontraktu RLS w CI.

---

## ADR-4: Trzy warstwy obrony przed jailbreakiem/nadużyciami

**Status:** zaakceptowane.

**Kontekst:** persony są edytowalne i udostępnialne między userami — dwuwarstwowe zabezpieczenie (preambuł + moderacja przy tworzeniu) chroni tylko `system_prompt` w momencie tworzenia, nie chroni przed jailbreakiem wpisanym jako wiadomość w trakcie czatu.

**Decyzja:** dodanie warstwy C — runtime guard (heurystyka + próbkowany klasyfikator) na każdej wiadomości czatu, plus recheck moderacji przy **każdej edycji** persony (nie tylko tworzeniu), plus `preamble_version` do wymuszenia re-checku po zmianie preambułu platformy.

**Konsekwencje:** dodatkowy koszt (heurystyka tania, klasyfikator tylko przy trafieniu) i tabela `moderation_events` z wymogami retencji/RBAC ze względu na potencjalnie wrażliwe treści (RODO).

---

## ADR-5: Autentykacja — wyłącznie Google OAuth, bez magic linka

**Status:** zaakceptowane (potwierdzone przez użytkownika).

**Kontekst:** oryginalna specyfikacja zakładała magic link + Google OAuth.

**Decyzja:** wyłącznie Google OAuth przez Supabase Auth. Upraszcza UI logowania i eliminuje potrzebę obsługi maili transakcyjnych na starcie.

**Konsekwencje:** brak fallbacku logowania dla userów bez konta Google — akceptowalne przy skali 2-5 znanych userów.

---

## ADR-6: `log_result` jako narzędzie batch, nie pojedynczy wpis

**Status:** zaakceptowane.

**Kontekst:** poleganie na tym, że model sam zbatchuje wiele wywołań `log_result` w jednej rundzie nie jest gwarantowanym zachowaniem — modele często wywołują narzędzia sekwencyjnie.

**Decyzja:** `log_result(entries: list[...])` przyjmujące 1-N wpisów w jednym wywołaniu, z walidacją i wynikiem per-entry (częściowy sukces możliwy).

**Konsekwencje:** limit rund tool-callingu (3-5) staje się czystym bezpiecznikiem przeciw pętlom, nie realnym ograniczeniem normalnej ścieżki (np. logowanie całego treningu).

---

## ADR-7: Bez rolling summary czatu w MVP

**Status:** zaakceptowane.

**Kontekst:** rolling summary (LLM-owa sumaryzacja starszej historii) wymaga osobnego async pipeline'u, wprowadza niedeterminizm i jest kosztem uzasadnionym dopiero przy realnie długich konwersacjach.

**Decyzja:** start z samym sliding window ostatnich M wiadomości. Rolling summary dodane później, data-driven, gdy produkcja pokaże realne ucinanie istotnego kontekstu.

**Konsekwencje:** przy bardzo długich sesjach czatu starszy kontekst będzie tracony bez streszczenia — akceptowalne ryzyko na start.

---

## ADR-8: Route guard "min. 1 aktywna persona" — odłożony

**Status:** zaakceptowane (potwierdzone przez użytkownika).

**Decyzja:** guard blokujący `/chat`/`/plans` bez aktywnej persony implementowany po tym, jak core flow (persony → czat → wyniki → plan) działa end-to-end, nie jako blocker pierwszej iteracji.

---

## ADR-9: Adherence tracking i wykresy w `/results` — w zakresie MVP

**Status:** zaakceptowane (potwierdzone przez użytkownika).

**Decyzja:** `/plans` day panel pokazuje "Zaplanowane" (plan_item) obok "Zrealizowane" (results z tego dnia) jako prosta juxtapozycja, bez złożonej analityki. `/results` dostaje wykresy trendu per metryka (`recharts`/shadcn `Chart`) — bez zmian schematu, tylko indeks `results_user_category_metric_date`.

---

## ADR-10: Cotygodniowy recap i integracje zewnętrzne — poza zakresem

**Status:** zaakceptowane (potwierdzone przez użytkownika).

**Decyzja:** cotygodniowy recap od persony — nie wchodzi do MVP, nie jest nawet planowany jako post-MVP. Import/synchronizacja Garmin/Strava/Apple Health — "może kiedyś", bez wpływu na architekturę teraz.

---

## ADR-11: Profil użytkownika (biometria) — wspólna tabela, wypełniana konwersacyjnie przez tool call

**Status:** zaakceptowane (potwierdzone przez użytkownika, dodane przed wdrożeniem na chmurę).

**Kontekst:** bez danych biometrycznych (waga, wzrost, wiek, poziom aktywności, cel) generowany trening/dieta nie może być realnie spersonalizowany. Wymóg: persona ma "dopytać" usera o te dane przy konfiguracji, nie wymagać wypełnienia formularza z góry.

**Decyzja:** wspólna, jedna na usera tabela `user_profile` (nie per-persona — dane biometryczne są wspólne niezależnie od tego, z którą personą user rozmawia; odróżnić od `personas.persona_constraints`, które jest specyficzne dla danej persony i **niedostępne dla end-usera** w API/UI — patrz `ai-pipeline.md`). Wypełniana przez nowe narzędzie `update_user_profile` (ta sama klasa co `log_result` — walidacja, częściowa aktualizacja, błąd wraca do modelu jako tool response), dostępne dla każdej persony. `ContextBuilder` wykrywa niekompletny profil i dokleja dynamiczną instrukcję "dopytaj naturalnie o brakujące dane" do promptu — znika automatycznie, gdy profil się uzupełni. Formularz `/profile` jako fallback dla userów wolących wypełnić dane wprost.

**Konsekwencje:** `PlanOrchestrator` (etapy 1-2) dostaje `user_profile` obok `persona_constraints` jako dodatkowy kontekst personalizacji. Brak kompletnego profilu nie blokuje generowania planu (zgodnie z ADR-8 — brak nowych twardych blokad w MVP), planner dostaje informację o brakach i może to zaznaczyć w notatkach planu.

---

## ADR-12: Limit aktywnych person — per konto, edytowalny przez admina (nie globalna stała)

**Status:** zaakceptowane.

**Kontekst:** limit 5 aktywnych person na usera był dotąd zakodowaną na sztywno stałą (trigger DB `enforce_persona_limit` + `PersonaService.MAX_ACTIVE_PERSONAS`). Przy 2-5 userach (Vercel Hobby) admin chce móc dać wybranemu userowi więcej (lub mniej) niż domyślne 5, bez zmiany kodu/deployu.

**Decyzja:** nowa kolumna `profiles.max_active_personas` (domyślnie 5, `CHECK` 0-50) — jedna wartość per konto, trwała niezależnie od okresu rozliczeniowego (celowo NIE w `usage_limits`, którego PK `(user_id, period_start)` resetuje się co miesiąc — złe miejsce na ustawienie mające trwać). Trigger `enforce_persona_limit` czyta wartość z `profiles` zamiast hardkodowanej `5`; `PersonaService.assert_can_activate_persona` w backendzie robi to samo przez `ProfilesRepo`, dając czytelny komunikat 409 przed uderzeniem w bazę. Admin edytuje przez `PATCH /api/v1/admin/users/{user_id}/persona-limit`, zapisywane w `admin_audit_log` (`action='edit_persona_limit'`) jak każda inna akcja administracyjna.

**Konsekwencje:** trigger w bazie pozostaje ostateczną linią obrony (spójne nawet przy buggy/pominiętej walidacji API), backend jest tylko szybszą, czytelniejszą warstwą przed nim — ten sam wzorzec co pierwotny limit "5". Wymaga `ProfilesRepo` (dotąd nieistniejące, blokowało też `require_admin`) — dodane w tej samej zmianie.

---

## ADR-13: "Ogólna rozmowa" (auto-routing) + wywołanie persony komendą `/slug`

**Status:** zaakceptowane (potwierdzone przez użytkownika, na bazie makiety `Coach App - Makiety.dc.html`).

**Kontekst:** makieta wprowadza tryb czatu nieprzypisany do jednej persony ("Ogólna rozmowa"), w którym
user zadaje pytanie bez wybierania konkretnego trenera, a system sam decyduje, kto ma odpowiedzieć —
oraz mechanizm jawnego wywołania konkretnej persony przez `/{slug} treść wiadomości`. Obecny model
(`chat_sessions.persona_id NOT NULL`, 1 persona/sesja, brak atrybucji persony per wiadomość) fizycznie
tego nie obsługuje. Pierwotna makieta pokazywała DWIE persony odpowiadające pod rząd na jedną
wiadomość — zespół (audyt architektoniczny + UX) zarekomendował uproszczenie do jednej persony na
turę ze względu na ryzyko dezorientacji usera (sprzeczne rady, niejasność "z kim rozmawiam") i koszt;
użytkownik potwierdził ten kierunek.

**Decyzja:**

- `chat_sessions.persona_id` nullable + `session_type` (`'persona'` | `'general'`) — sesja `general`
  ma `persona_id = NULL` (schemat skonsolidowany w `0001_init.sql` — patrz uwaga w nagłówku
  tego pliku migracji: projekt nie był jeszcze wdrożony, więc historia przyrostowych ALTER-ów
  z wczesnych iteracji została scalona w jedną bazową migrację zamiast trzymana osobno).
- `chat_messages.persona_id` (atrybucja per wiadomość — w sesji `general` różne wiadomości `assistant`
  mogą pochodzić od różnych person) + `chat_messages.invoked_via` (`'auto_routed'` | `'slash_command'`).
- `personas.slug`, unikalny per user, generowany z `type + name` przy tworzeniu i **regenerowany przy
  zmianie nazwy** (kolizje rozwiązywane numerycznym suffixem w `PersonaService`).
- **Routing — jedna lub wiele person sekwencyjnie na turę użytkownika** (max 3 przy
  auto-routingu), wybierane przez lekki "menadżer rozmowy": (1) parsowanie jednego lub
  wielu `/slug` na początku wiadomości (kolejność = kolejność odpowiedzi,
  `invoked_via='multi_slash'` gdy ≥2); (2) w braku slashy — klasyfikator zwraca
  `persona_ids[]` (1..N gdy pytanie styka się z ≥2 rolami); (3) każda wybrana persona
  odpowiada przez ISTNIEJĄCY `ChatOrchestrator.handle_message` sekwencyjnie —
  wiele `persona_turn_start`, **jedno** `done` na końcu.
- **Fallback przy niepewnym/braku trafienia klasyfikatora:** persona, która ostatnio odpowiadała w tej
  sesji `general` (kontynuacja kontekstu); jeśli to pierwsza wiadomość sesji bez wcześniejszej historii
  — pierwsza aktywna persona usera (deterministyczne, bez dodatkowego pytania zwrotnego w MVP).
- `ContextBuilder` budując system prompt dla persony X w sesji `general` filtruje historię: wszystkie
  `role='user'` (wspólne) + `role in ('assistant','tool')` WHERE `persona_id = X` — inaczej persona X
  "widziałaby" w historii odpowiedzi innych person jako własne.
- Kontrakt SSE (`architecture.md` §3) rozszerzony o `persona_id`/`persona_label` w eventach oraz
  event `persona_turn_start {persona_id, persona_label}` przed tokenami każdej tury persony.
- Frontend: input czatu w sesji `general` ma autouzupełnianie po wpisaniu `/`; przy multi-reply
  finalizuje poprzednią odpowiedź do cache historii przed kolejnym `persona_turn_start`.
- Toole planu w czacie: `get_plan`, `upsert_plan_items`, `rebuild_plan` (pełny pipeline 1–3).

**Konsekwencje:** multi-persona zwiększa koszt/latencję (N wywołań LLM) względem pierwotnego
uproszczenia „1 persona”; limit 3 oraz sekwencyjność chronią UX i budżet. Wymaga statusów
streamu (Faza 1) i aktualizacji `frontend.md` / `ai-pipeline.md`.

---

## ADR-14: Katalog ćwiczeń — nowa domena treści referencyjnych

**Status:** zaakceptowane (potwierdzone przez użytkownika).

**Kontekst:** makieta (zakładka Ustawienia, `catalogExercisesAll`) pokazuje przeszukiwalną galerię
ćwiczeń (kategorie, poziom trudności, opis wykonania, częste błędy, zdjęcie), powiązaną z typem persony
(trener motoryczny / trener badmintona). To całkowicie nieobecna domena w obecnym schemacie bazy.

**Decyzja:** nowa tabela `exercises` (migracja `0002_exercise_catalog.sql`) — statyczna treść
referencyjna, seedowana migracją (analogicznie do `persona_templates`/`plan_templates`), bez własnego
serwisu domenowego (brak logiki biznesowej poza filtrowaniem — cienki router + repozytorium
wystarczą). Kategorie jako `text[]` (mała, znana z góry lista, bez osobnej tabeli słownikowej). Jeden
endpoint `GET /exercises` zwracający pełne obiekty (katalog rzędu kilkudziesięciu pozycji — brak
potrzeby paginacji/detail-fetch). Zdjęcia w Supabase Storage (bucket publiczny `exercise-photos`),
dodawane ręcznie przy seedowaniu — brak endpointu uploadu w MVP. **Katalog pozostaje w zakładce
Ustawienia** (zgodnie z makietą — użytkownik świadomie utrzymał to umiejscowienie mimo alternatywy
zaproponowanej w audycie UX, tj. osobnej trasy linkowanej z `/plans`/konfiguracji persony).

**Konsekwencje:** RLS SELECT publiczne dla `authenticated`, brak INSERT/UPDATE/DELETE dla zwykłego
usera (treść zarządzana wyłącznie przez migracje/seed, jak pozostałe "gotowce"). Edytowalność przez
admina/użytkownika — świadomie odłożona, wymaga osobnej decyzji gdy pojawi się taka potrzeba.

---

## ADR-15: `/settings` — ustawienia konta (nick, motyw) jako nowa trasa

**Status:** zaakceptowane (potwierdzone przez użytkownika).

**Kontekst:** makieta wprowadza zakładkę Ustawienia z edycją nicku i przełącznikiem motywu
jasny/ciemny, nieobecną w `frontend.md` §1 (routing) ani w `profiles`.

**Decyzja:** nowa kolumna `profiles.nick` (nullable, fallback do nazwy z Google OAuth — migracja
schemat skonsolidowany w `0001_init.sql`), nowy, oddzielny endpoint `GET/PATCH /api/v1/account`
(celowo NIE rozszerzenie `/api/v1/profile`, zarezerwowanego pod biometrię usera — ADR-11, inna
odpowiedzialność). Motyw jasny/ciemny: **bez persystencji w bazie** — czysto `localStorage` po stronie
frontendu; przy skali kilku znanych userów i typowo jednym urządzeniu synchronizacja między
urządzeniami nie uzasadnia round-tripu do API. Katalog ćwiczeń (ADR-14) współdzieli tę stronę w UI, ale
pozostaje niezależną domeną API.

**Konsekwencje:** nowa trasa `/settings` (chroniona, auth) w `frontend.md` §1. Jeśli w przyszłości motyw
ma być trwały między urządzeniami — trywialne dodanie `profiles.theme` bez wpływu na resztę
architektury.

---

## ADR-16: Limit użycia jako budżet w USD per konto (nie plany Free/Pro)

**Status:** zaakceptowane (potwierdzone przez użytkownika).

**Kontekst:** makieta panelu admina pokazywała zużycie jako kwotę dolarową z etykietą planu
("Free"/"Pro" — `$4.20 / $10.00`), co sugerowało płatne plany subskrypcyjne nieobecne nigdzie indziej
w specyfikacji (MVP ma być non-commercial, `usage_limits` śledziło dotąd tylko liczby: wiadomości,
tokeny, generacje planu). Użytkownik doprecyzował: kwota dolarowa ma być **realnym, egzekwowanym
budżetem ochronnym przed nadmiernym zużyciem API** (nie mechanizmem rozliczeniowym/subskrypcyjnym) —
domyślnie $10 na konto, edytowalnym przez admina. Etykiety planów "Free"/"Pro" z makiety odrzucone jako
mylące (sugerują subskrypcję, której nie ma).

**Decyzja:** nowa kolumna `profiles.usage_budget_usd` (domyślnie `10.00`, `CHECK` 0-1000) — wzorzec
identyczny jak `profiles.max_active_personas` (ADR-12): jeden wiersz per konto, trwały niezależnie od
okresu rozliczeniowego, edytowalny przez admina (`PATCH /api/v1/admin/users/{user_id}/usage-budget`,
zapisywane w `admin_audit_log` jak każda inna akcja administracyjna). Nowa kolumna
`usage_limits.cost_usd_used` — faktyczny koszt zużyty w bieżącym okresie, liczony z odpowiedzi
OpenRoutera (`prompt_tokens`/`completion_tokens` × cennik modelu, pobierany i cache'owany z
`/api/v1/models` OpenRoutera — nie hardkodowany). `UsageLimitService.check_and_increment_message`
odrzuca (429) gdy `cost_usd_used + szacowany_koszt_tury > usage_budget_usd`, analogicznie do
istniejącego mechanizmu liczników. Kolumna `usage_limits.tier` (niewykorzystany koncept planów)
usunięta.

**Konsekwencje:** panel admina pokazuje `cost_usd_used`/`usage_budget_usd` (kwota + edytowalny limit),
BEZ etykiet "Free"/"Pro". Wymaga rozszerzenia `ai-pipeline.md` o sposób liczenia kosztu z cennika
OpenRoutera i utrzymywania cache'u cen modeli.

---

## ADR-17: Kierownik Zespołu (Goat) — koordynacja sesji `general`

**Status:** zaakceptowane (wdrożone 2026-08-04; **nowelizowane 2026-08-16**).

**Kontekst:** W sesji `general` (ADR-13) klasyfikator routingu wybierał persony, ale każda
odpowiadała w izolacji — bez briefu kierownika. Potem (2026-08-04) Goat robił relay cytatów
trenerów (`format_goat_relay`) — feeling „odzywa się dietetyk” przy pytaniu o motorykę.
User oczekuje rozmowy **z kierownikiem**; eksperci tylko na żądanie Goata albo przez `/slug`.

**Decyzja:**

- **Goat** — systemowa rola (`TeamLeadSpeaker`, prompt w kodzie). Nie jest personą usera w DB.
- **Widoczność (2026-08-16):** W `general` bez slashy **jedna tura** `TeamLeadSpeaker`
  (`persona_id=null`). Specjalista: tool **`consult_persona`** (slug z rosteru aktywnych person
  **tego usera** — w tym `custom`; backstage, bez widocznej wiadomości trenera). Status UX:
  `Goat konsultuje z {etykieta}…`. Roundtable = N consultów + **jeden** bubble Goata.
- **Wyjątek:** `/slug` / multi-slash / sesja `persona` — user widzi personę bezpośrednio; Goat
  nie startuje.
- **Plan:** Goat woła `rebuild_plan` w swojej turze (bez osobnej pętli trenerów jako mówców).
- **Narzędzia:** Goat — `get_plan`, `rebuild_plan`, `update_user_profile`, `consult_persona`
  (max 5/turę); trenerzy — reszta **bez** `rebuild_plan` i `consult_persona`.
- **Granice ról:** `[ZAKRES ROLI]` (`persona_scope.py`) + overlay safety (migracja `0009`).
- **Kontekst:** `ContextBuilder` dokleja `[PLAN TRENINGOWY]` i `[OSTATNIE WYNIKI UŻYTKOWNIKA]`.
- **SSE:** `persona_status` / `tool_result` dla consult z etykietą Goata; `persona_id: null`.
- **Tura w tle:** `chat_sessions.turn_in_progress`; FE: `useChatTurnRunner` w AppShell.

**Konsekwencje:** 0..N dodatkowych wywołań LLM tylko gdy Goat woła `consult_persona` (nie zawsze
+1 klasyfikator JSON). ADR-13 pozostaje źródłem prawdy dla modelu sesji i `/slug`.
Dokumentacja: `docs/technical/team-lead.md`. Spec: `docs/superpowers/specs/2026-08-16-goat-consult-persona-design.md`.

**Supersedes (2026-08-16):** `format_goat_relay`, `TeamLeadService.plan_consultation` jako wybór
mówcy, bypass „1 aktywna persona = tura tej persony”, design „kierownik niewidoczny”.

---

## ADR-18: Mobile viewport — `dvh` + visualViewport, bez page-scroll na czacie

**Status:** zaakceptowane (2026-08-16).

**Kontekst:** Na telefonach Android/iOS historia czatu nie była widoczna od razu. `h-svh` +
`main overflow-y-auto` + trzy poziomy `overflow-hidden` zjadały wysokość `MessageList`.
Wirtualizacja (`estimateSize: 88`) i `scrollToIndex` w `useEffect` startowały od złego
offsetu. Brak `viewport-fit=cover` i `env(safe-area-inset-*)`.

**Decyzja:**

- Shell: `h-dvh` + CSS var `--app-height` z `window.visualViewport` (klawiatura kurczy layout).
- Na `/chat` i `/chat/:id` `main` = `overflow-hidden flex flex-col`; inne trasy zostają
  `overflow-y-auto`.
- Historia: kotwica na dole (`scrollIntoView`), bez wirtualizacji w MVP.
- Composer i strony: safe area; touch target ≥44px.
- Bottom nav (Czat / Plan / Wyniki) — odłożone; nie dopieszczamy 6-linkowego paska jako
  „docelowej” IA na telefon.

**Konsekwencje:** czat nie scrolluje całej strony; inne ekrany scrollują w `main`. Bottom
nav to osobna zmiana IA (kolejny sprint).

