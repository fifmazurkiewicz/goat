# Warstwa AI — modele, moderacja, generowanie planu

## 0. Profil użytkownika — personalizacja (waga, wzrost, wiek, cel)

**Problem:** bez danych biometrycznych (waga, wzrost, wiek, płeć, poziom aktywności, cel) żadna persona nie może realnie spersonalizować treningu/diety — czysto konwersacyjne "opowiedz mi o sobie" bez struktury nie daje danych, na których można niezawodnie oprzeć prompt plannera.

**Decyzja:** wspólna, jedna na usera tabela `user_profile` (nie per-persona — waga jest jedna, niezależnie od tego z którym trenerem user rozmawia). Odróżnij od `personas.persona_constraints`, które jest specyficzne dla danej persony (np. "unikaj przysiadów" zgłoszone akurat trenerowi siłowni).

**Wypełnianie — konwersacyjnie, tool call, nie statyczny formularz jako główna ścieżka.** Zgodnie z założeniem "persona ma dopytać usera o szczegóły": każda persona ma dostęp do narzędzia `update_user_profile`, tej samej klasy co `log_result` (patrz sekcja 2) — model woła je, gdy user poda dane w naturalnej rozmowie, nie wymagając od usera wypełniania formularza przed pierwszą rozmową.

```python
def update_user_profile(
    height_cm: float | None = None,
    weight_kg: float | None = None,
    date_of_birth: str | None = None,       # ISO 8601 date
    sex: Literal["male", "female", "other"] | None = None,
    activity_level: Literal["sedentary", "light", "moderate", "active", "very_active"] | None = None,
    primary_goal: Literal["lose_weight", "build_muscle", "improve_endurance", "general_health", "sport_specific"] | None = None,
    notes: str | None = None,
) -> dict: ...
```

Częściowa aktualizacja (tylko podane pola), walidacja zakresów jak w tabeli `user_profile` (`height_cm` 100-250, `weight_kg` 20-400, enumy dla `sex`/`activity_level`/`primary_goal`) — błąd walidacji wraca do modelu jako tool response, nie wyjątek (ten sam wzorzec co `log_result`).

**Intake instruction — dopytywanie na starcie rozmowy.** `ContextBuilder` (architecture.md sekcja 5) sprawdza kompletność `user_profile` (krytyczne pola: `height_cm`, `weight_kg`, `date_of_birth`, `activity_level`, `primary_goal`) przed zbudowaniem system promptu. Jeśli brakuje — dokleja do promptu dynamiczną instrukcję (NIE część preambułu platformy, osobny, generowany segment):

```
[KONTEKST: PROFIL UŻYTKOWNIKA NIEKOMPLETNY]
Brakuje: {lista brakujących pól po polsku, np. "waga, wzrost, poziom aktywności"}.
Zanim przejdziesz do właściwego coachingu, dopytaj naturalnie o brakujące dane w
1-2 pierwszych wiadomościach tej rozmowy (nie jako sztywna ankieta). Gdy user je
poda, zapisz je narzędziem update_user_profile. Nie blokuj rozmowy, jeśli user nie
chce podać któregoś pola — kontynuuj z tym, co masz.
```

Ta instrukcja znika automatycznie z promptu, gdy profil jest kompletny — nie wymaga osobnej logiki "czy to pierwsza rozmowa", tylko stanu danych.

**Fallback API** — `GET`/`PATCH /api/v1/profile` (bez zakładki w nav; biometria głównie przez czat). Obie ścieżki piszą do tej samej tabeli.

**Zasilanie generowania planu.** `user_profile` przekazywany explicite do plannera (etap 1 i 2, architecture.md sekcja 4) obok `persona_constraints` — dane biometryczne wpływają np. na cele kaloryczne (dietetyk), dobór obciążeń adekwatny do wieku/poziomu (trener siłowni). Brak kompletnego profilu **nie blokuje** generowania planu (zgodne z ADR-8 — nie dodajemy nowych twardych blokad w MVP), ale planner dostaje informację o brakach i może w notatkach zaznaczyć że plan jest wstępny/ogólny do czasu uzupełnienia danych.

## 1. Modele (weryfikować przez `/api/v1/models` OpenRoutera w runtime, nie hardkodować cen)

| Rola | Model domyślny | Uzasadnienie |
|---|---|---|
| `chat_model` | `anthropic/claude-haiku-4.5` | szybki/tani, stabilny tool calling + streaming |
| `PLANNER_MODEL` | `anthropic/claude-sonnet-4.6` | jakość + natywny `response_format: json_schema` ze `strict: true` |

Fallback lista min. 2 dostawców dla `chat_model` (np. `[anthropic/claude-haiku-4.5, openai/gpt-5-mini]`) — awaria jednego providera nie wywala czatu. `require_parameters: true` w provider routing OpenRoutera dla plannera (żeby nie routować do endpointu bez wsparcia `json_schema`).

Orientacyjny koszt: ~$0.003/wiadomość czatu, ~$0.15-0.20/generację planu tygodniowego dla 5 person (3-etapowy pipeline).

## 1a. Routing person w "Ogólnej rozmowie" (ADR-13)

`ChatRoutingService` (`app/domain/chat/routing.py`) wybiera dokładnie jedną personę odpowiadającą w
sesji `general`, gdy user nie użył `/slug` (parsowanie `/slug` jest deterministyczne, bez LLM — patrz
`architecture.md` §3a).

- **Model:** `chat_model` (tani/szybki — routing ma być niezauważalny kosztowo, analogicznie do
  moderacji), NIE `PLANNER_MODEL`.
- **Format:** `response_format: json_schema`, `{"persona_id": str}` — schemat ograniczony do ID
  aktywnych person usera w danej sesji (enum w schemacie, nie wolny tekst — model nie może zwrócić
  nieistniejącego ID).
- **Input:** krótkie opisy ról aktywnych person (kicker/typ + pierwsze zdanie `system_prompt`), NIE
  pełne system prompty — routing nie potrzebuje pełnego kontekstu persony, tylko jej domeny.
- **Fallback** (niepewność/brak trafienia): persona ostatnio odpowiadająca w tej sesji, a przy braku
  historii — pierwsza aktywna persona usera. Bez pytania zwrotnego do usera w MVP.
- **Golden cases** dla routingu (analogicznie do sekcji 5 — moderacja): zestaw pytań jednoznacznie
  przypisanych do jednej domeny (np. pytanie o dietę → dietetyk) jako regression fixture w CI,
  metryka: accuracy trafień na zestawie referencyjnym.

## 1b. Koszt LLM i budżet USD (ADR-16)

Każda odpowiedź OpenRoutera w streamie SSE musi zawierać finalny chunk `usage`
(`prompt_tokens`/`completion_tokens`) — wymaga `usage: {include: true}` w body requestu (domyślnie
OpenRouter nie dołącza `usage` do streamowanych odpowiedzi). Koszt tury liczony jako
`prompt_tokens * cena_input + completion_tokens * cena_output` wg cennika modelu.

**Cennik modeli** pobierany z `GET /api/v1/models` OpenRoutera przy starcie aplikacji i cache'owany
in-memory (odświeżany okresowo, np. co godzinę) — ceny modeli na OpenRouterze zmieniają się, więc
NIE są hardkodowane w kodzie. Fallback: jeśli model nie występuje w aktualnym cache cennika (np.
chwilowa awaria endpointu `/models`), użyj ostatniej znanej wartości z cache; jeśli cache pusty (zimny
start) — konserwatywne oszacowanie górnej granicy, żeby nie ominąć limitu przy braku danych.

Suma kosztu zapisywana w `usage_limits.cost_usd_used` (atomowy check+increment, `architecture.md`
§9), egzekwowana względem `profiles.usage_budget_usd` (domyślnie $10, edytowalny przez admina).
Generowanie planu (3 etapy × do 5 person równolegle w etapie 2) sumuje koszt wszystkich wywołań tego
samego joba do tej samej puli.

## 2. `log_result` — narzędzie jako batch

**Decyzja:** `log_result(entries: list[{category, metric, value, unit, date, notes}])`, nie pojedynczy wpis. Trening z 5 ćwiczeniami = 1 wywołanie narzędzia = 1 runda, niezależnie od tego czy model sam zdecyduje się zbatchować wywołania (nie jest to gwarantowane zachowanie — modele często wywołują narzędzia sekwencyjnie nawet gdy niezależne). Walidacja per-entry, częściowy sukces możliwy (3/5 przechodzi, 2 wracają jako błąd do modelu w tym samym tool response, nie failuje cały batch).

Walidacja przez `allowed_metrics` (cache in-memory, ładowana na starcie appki — hot-path w trakcie streamingu) z fallbackiem `is_custom=true`.

## 3. Kontekst czatu — token budget

```
[platform preambuł + persona system_prompt]      ~500-1500 tok. (stałe)
[kontekst wyników: ostatnie N wpisów, tabela]     ~200-500 tok.
[K ostatnich surowych wiadomości — sliding window] do wypełnienia budżetu
[bieżąca wiadomość usera]
```

`MAX_INPUT_TOKENS` per `chat_model` jako twardy target (np. 6-10k, niezależnie od tego że model wspiera 128k+ — kwestia kosztu/latencji, nie limitu modelu). Bez rolling summary w MVP (patrz [`architecture.md`](architecture.md#5-kontekst-czatu--zarządzanie-tokenami)).

## 4. Generowanie planu — 3 etapy, priorytet: synchronizacja

Pełny opis pipeline'u w [`architecture.md`](architecture.md#4-generowanie-planu--pipeline-decyzja-priorytet-to-synchronizacja-między-personami). Kluczowe dla warstwy AI:

**Etap 3 (harmonizacja)** to nowy, dedykowany krok pełniący rolę "wirtualnego zarządcy kalendarza" — dostaje complet draft plan_items ze wszystkich person naraz i:
- wykrywa konflikty obciążenia (np. ciężki trening nóg + długi bieg tego samego dnia),
- sprawdza spójność diety z planem treningowym (dzień intensywny → odpowiednio wyższy target kaloryczny/węglowodanowy),
- pilnuje że dni odpoczynku są faktycznie uwzględnione,
- dopisuje cross-referencing notes między personami (np. dietetyk odnosi się do treningu tego dnia),
- output jako **targeted patch** do konkretnych `plan_items` (koryguje tylko to co wymaga korekty), nie pełna regeneracja wszystkiego — kontrola kosztu.

### `persona_constraints` — twarde ograniczenia niezależne od czatu

Plan bazuje wyłącznie na `results` + poprzednim planie, nie na historii czatu (zbyt niedeterministyczne). Problem: kontuzja / zalecenie lekarskie wspomniane tylko w czacie nigdy nie trafi do plannera bez dedykowanego mechanizmu. **Rozwiązanie:** pole `personas.persona_constraints` — krótka notatka twardych ograniczeń (np. uraz, zakaz ćwiczenia), przekazywana do plannera **explicite** w każdym etapie (2 i 3) oraz do `ContextBuilder` czatu, oddzielona od reszty kontekstu.

**Dostęp (świadoma decyzja produktowa):** pole jest **wyłącznie systemowe / operatorskie** — end-user **nie widzi** go w UI ani w odpowiedziach API (`PersonaOut` go nie zwraca) i **nie może** go ustawić przez `POST/PATCH /personas` (pole usunięte z DTO create/update; serwis dodatkowo odrzuca próbę zapisu). Wypełnianie: seed/admin/przyszły panel operatorski albo bezpośredni zapis w DB — nie formularz persony.

### `safety_prompt` gotowca — reguły medyczne osobno od zachowania

Obok `persona_constraints` (per-instancja persony) gotowiec ma stały overlay w `app_private.persona_template_safety`, doklejany przy czacie/planie po `base_template_id` (połączenie `service_role`). `default_prompt` / `system_prompt` zawierają wyłącznie zachowanie. Spec: `docs/superpowers/specs/2026-08-04-persona-safety-prompt-design.md`.

## 5. Golden test cases (regresja w CI)

**Moderacja/jailbreak-guard** — ~30-50 przypadków w kategoriach: benign / borderline / jawny jailbreak / red-flag mid-chat / obfuskacja (roleplay-wrapper, inny język, "w formie wiersza"). Metryka bramkująca: recall 100% na jailbreak/red-flag jako blocker deploya, false-positive rate na benign z progiem (np. <5%). Trzymane jako fixture'y + `pytest`, uruchamiane w CI przy każdej zmianie preambułu/klasyfikatora.

**Jakość planu** — golden set 5-10 kanonicznych profili user+persona+results:
- Asercje deterministyczne jako twarda bramka: zgodność z `json_schema`, wszystkie dni okresu pokryte, metryki z `allowed_metrics` istnieją, brak duplikatów, wartości w granicach `value_min/value_max`.
- LLM-as-judge (tani model oceniający sensowność/progresję/spójność międzypersonową) jako sygnał kierunkowy, **nie** twarda bramka CI (zbyt niestabilne jako gate) — alert do przeglądu.
- Fixture'y z realnych (zanonimizowanych) promptów/odpowiedzi zbierane okresowo z produkcji jako regression replay.

## 6. Mockowanie OpenRoutera w testach

`respx` (mockuje `httpx` na poziomie transportu, działa ze streamingiem) + ręcznie nagrane fixture'y surowych chunków SSE z realnych odpowiedzi (zanonimizowane, zapisane jako `.txt`/`.jsonl`). Nie VCR.py — słabe wsparcie dla async streamingu.

## 7. Odporność na awarie OpenRoutera

`tenacity` retry+backoff na transporcie **tylko przed pierwszym bajtem odpowiedzi** (streamu nie da się bezpiecznie powtórzyć po wysłaniu części tokenów do klienta). Fallback lista modeli w provider routing OpenRoutera.

## 8. Poza zakresem MVP (świadomie odłożone)

- **Cotygodniowy recap od persony** — nie wchodzi do MVP (decyzja).
- **Import/synchronizacja Garmin/Strava/Apple Health** — "może kiedyś", generyczny model `results` już to udźwignie bez zmian schematu gdy przyjdzie czas.
