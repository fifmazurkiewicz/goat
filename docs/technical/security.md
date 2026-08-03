# Bezpieczeństwo

## 1. Jailbreak / nadużycia — trzy warstwy

Aplikacja pozwala userom pisać własne persony i je udostępniać innym — realne ryzyko prompt injection / próby zmiany roli modelu. Traktowane jako wymaganie bezpieczeństwa, nie dodatek.

**Warstwa A — stały platform preambuł + safety gotowca (server-side, nieedytowalne).**
System prompt wysyłany do modelu =

`[PLATFORM PREAMBUŁ]` + opcjonalnie `[ZABEZPIECZENIA GOTOWCA]` + `[ZACHOWANIE PERSONY]`.

- Preambuł: `app/domain/chat/preamble.py` (`PREAMBLE_VERSION`).
- Zabezpieczenia gotowca (lekarz, leki, „czego NIE robisz”, red flags per typ): tabela
  `app_private.persona_template_safety` — **brak GRANT** dla `anon`/`authenticated`;
  odczyt tylko przez `service_role` w backendzie. Nie wraca w `GET /persona-templates`.
- Zachowanie: `personas.system_prompt` (edytowalne w UI jako „Jak ma się zachowywać”).
- `persona_constraints`: systemowe, nie w `PersonaOut` / create|update DTO.

Szczegóły: [`docs/superpowers/specs/2026-08-04-persona-safety-prompt-design.md`](../superpowers/specs/2026-08-04-persona-safety-prompt-design.md).

`preamble_version` w tabeli `personas` pozwala wymusić re-check wszystkich person po zmianie preambułu platformy, niezależnie od tego czy user zmieniał swój prompt.

**Świadome ograniczenie MVP (Data API):** kolumna `personas.persona_constraints` nadal istnieje w `public` z RLS „własne wiersze”. Aplikacja goat nie czyta person przez Supabase JS (tylko REST backend), więc UI nie wycieka — ale klient z JWT usera *teoretycznie* mógłby odczytać własny constraints przez PostgREST. Pełne ukrycie kolumny = osobny widok / private schema (backlog).

**Warstwa B — moderacja LLM-klasyfikatorem.** Przy tworzeniu, **każdej edycji** (nie tylko tworzeniu) i obowiązkowo przy `is_shared=true`: dodatkowe wywołanie LLM klasyfikujące czy opis persony mieści się w zakresie coachingu, czy próbuje zmienić rolę/ominąć ograniczenia. Wynik → `personas.moderation_status`. Cache po `moderation_checked_prompt_hash` (hash tylko sekcji usera) — nie re-moderuj niezmienionej treści.

**Warstwa C — runtime guard w czacie (nowa, krytyczna).** Warstwy A i B chronią tylko `system_prompt` persony w momencie tworzenia/edycji — nie chronią przed jailbreakiem wpisanym jako zwykła wiadomość w trakcie rozmowy. Mechanizm: tania heurystyka regex/keyword na **każdej** wiadomości usera ("ignore previous instructions", "jesteś teraz", "zapomnij o zasadach", "DAN"...) + próbkowany/warunkowy klasyfikator LLM przy trafieniu. Ta sama heurystyka obejmuje pola `is_custom` w `results` (freeform `metric`/`unit`/`notes`) — to wektor, który nie jest objęty ani przez runtime guard wiadomości, ani przez moderację persony.

Trafienia logowane do `moderation_events`. **Retencja/RBAC:** `raw_snippet` może zawierać bardzo wrażliwe treści (myśli samobójcze, zaburzenia odżywiania) — dostęp ograniczony do wąskiego zespołu review, retencja czasowa do ustalenia przed produkcją, dla non-flagged przypadków rozważyć hash+metadata zamiast surowej treści.

**Znane, świadomie zaakceptowane ograniczenie MVP:** warstwy A-C adresują input usera (jailbreak). Nic nie chroni przed tym, że sam model wygeneruje ryzykowną poradę bez żadnego jailbreaku (np. drastyczny deficyt kaloryczny) — na MVP wystarcza prompt engineering w sekcji 3 preambułu, output filtering odłożony.

## 2. RLS jako rzeczywista bariera, nie fikcja

Backend łączy się per-request jako authenticated user (RLS context ustawiany z JWT przez `SET LOCAL` + `set_config`, patrz [`architecture.md`](architecture.md#2-baza-danych--dostęp-i-rls)) dla wszystkich operacji per-user. `service_role` wyłącznie do Supabase Admin API i `/admin/*`, z jawną kodową weryfikacją `profiles.is_admin`. Jeśli backend domyślnie łączyłby się przez service role "dla wygody", RLS przestałby cokolwiek chronić — każdy bug w kodzie staje się potencjalnym wyciekiem danych między userami.

**Obowiązkowy test kontraktu RLS**: integracyjny test ustawiający claims usera A, wstawiający dane, przełączający na usera B i asercjujący że repo nie widzi cudzych wierszy.

## 3. Walidacja tool calls przed zapisem

Argumenty `log_result` generowane przez model to **niezaufany input** mimo że pochodzą z "naszego" modelu. Walidacja przez tabelę referencyjną `allowed_metrics` (typ/jednostka/zakres) z fallbackiem `is_custom=true` przy nieznanej metryce (sanity checks: skończona liczba, unit max 20 znaków, notes max 500 znaków, data nie z przyszłości). Błąd walidacji wraca do modelu jako tool response, nie wyjątek serwera.

## 4. Rate limiting i koszt-DoS

- Atomowy check+increment `usage_limits` (`UPDATE ... WHERE used < limit RETURNING` w jednym query) — chroni przed race condition przy równoległych requestach.
- Twardy `max_tokens` per endpoint (czat vs planner), nigdy poleganie na domyślnym.
- Limit 3-5 rund tool-calling per wiadomość (z `log_result` jako batch — patrz [`ai-pipeline.md`](ai-pipeline.md) — limit rund staje się bezpiecznikiem przeciw pętlom, nie realnym ograniczeniem normalnej ścieżki).
- Cap długości wiadomości usera.
- `request.is_disconnected()` + cancel zadania przy rozłączeniu klienta w trakcie streamu — nie płacić za tokeny generowane po zamknięciu karty.
- Partial unique index `one_active_job_per_user` — max 1 aktywny job generowania planu na usera, na poziomie bazy (nie check-then-insert w aplikacji).
- Generowanie planu debituje z tego samego `usage_limits` co czat.
- Coarse rate limiting per-minutowy (osobno od miesięcznego `usage_limits`) — do rozważenia w implementacji (np. `slowapi` albo prosty in-memory limiter).

## 5. CORS i sekrety

CORS jako jawny allowlist (domena Vercel + finalna domena), nigdy wildcard, zwłaszcza przy nagłówku `Authorization`. Pełna lista sekretów i zasady rotacji w [`devops.md`](devops.md#5-sekrety-i-zmienne-środowiskowe).
