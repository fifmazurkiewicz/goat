# Audyt: Goat (Kierownik Zespołu) — 2026-08-04

**Zakres:** sesja `general`, koordynacja multi-persona, operacje na planie, SSE, granice ról.  
**Referencje:** [ADR-17](../adr/decisions.md#adr-17-kierownik-zespołu-goat--koordynacja-sesji-general), [team-lead.md](../team-lead.md).

## Metadane audytu

| Pole | Wartość |
|------|---------|
| Data wykonania | 2026-08-04 |
| Środowisko | code review (local) |
| Wykonawca | zespół agentów (architektura, AI/Python, frontend, docs) |
| Migracje wymagane | `0008_background_jobs`, `0009_persona_role_boundaries`, `0010_drop_personas_chat_model` |

## Werdykt

**Pass z uwagami (P1/P2)** — happy path działa; dokumentacja i testy uzupełnione w tej sesji. Pozostają trade-offy UX i dług techniczny routingu.

---

## 1. Co działa dobrze

1. **Podział ról** — Goat ma wyłącznie `get_plan` + `rebuild_plan`; trenerzy bez `rebuild_plan`.
2. **Widoczność w UI** — etykieta „Goat · Kierownik Zespołu” przy operacjach planu (`persona_id=null` w DB/SSE).
3. **Koordynacja między trenerami** — brief kierownika + `prior_summaries` w jednej turze.
4. **Bypass deterministyczny** — slash/multi-slash i 1 persona omijają LLM konsultacji.
5. **Granice ról** — `persona_scope.py` + migracja `0009` we wszystkich template safety.

---

## 2. Ryzyka i luki

| # | Opis | Severity | Status |
|---|------|----------|--------|
| 1 | **Multi-slash + plan-only** — `/dietetyk /trener ułóż plan` → tylko Goat, trenerzy pominięci mimo slashy. Świadomy trade-off (plan = Goat), ale może mylić usera. | Średnia | Udokumentowane w [team-lead.md](../team-lead.md) |
| 2 | **Podwójny koszt LLM** przy plan-only | Średnia | **Zrobione** — `build_plan_only_consultation` pomija LLM konsultacji |
| 3 | **Heurystyki planu** — substring matching; ryzyko false positive/negative. | Średnia | Testy w `test_team_lead.py` |
| 4 | **`ChatRoutingService` martwy** | Średnia | **Zrobione** — deprecated w `routing.py` |
| 5 | **Fallback konsultacji** — błąd LLM → pierwsza persona, nie „ostatnio odpowiadająca” (ADR-13). | Średnia | P2 |
| 6 | **Retry nie idempotentny** — ponowne `rebuild_plan` przy retry streamu. | Średnia | Udokumentowane |
| 7 | **Sesja persona + plan** — brak `rebuild_plan` w czacie 1:1. | Niska | Udokumentowane w team-lead.md |
| 8 | **`invoked_via=team_lead`** mapowane na `auto_routed` w DB. | Niska | Observability |

---

## 3. Checklist weryfikacji manualnej

### Backend — flow kierownika

- [ ] `TeamLeadService.plan_consultation` — LLM wybiera 1..N person (≥2 aktywne persony)
- [ ] Bypass `/slug` — deterministyczny wybór
- [ ] Bypass multi-slash — kolejność = kolejność slashy
- [ ] 1 aktywna persona — bez LLM kierownika
- [ ] `team_phase`: `planning` → `delegating`
- [ ] `team_status` z `consultation.status_message`

### Backend — ścieżka planu (Goat widoczny)

- [ ] „Generuj zharmonizowany plan na sierpień” → tylko Goat, bez dietetyka
- [ ] „Ułóż plan i co jeść” → Goat + trenerzy
- [ ] Goat nie ma `log_result` / `update_user_profile`
- [ ] Trenerzy nie wołają `rebuild_plan` po `[NOTATKA KIEROWNIKA]`
- [ ] Wiadomość Goata: `persona_id=NULL`

### Frontend

- [ ] Nagłówek „Goat · Kierownik Zespołu” w historii i streamingu
- [ ] Status „Goat analizuje…” przed tokenami
- [ ] Trenerzy nadal z etykietą `Imię · Rola`

### Testy automatyczne (2026-08-04)

- [x] `backend/tests/test_team_lead.py`
- [x] `backend/tests/test_orchestrator_team_lead.py`
- [x] `backend/tests/test_chat_tools_schema.py`
- [x] `backend/tests/test_persona_scope.py`
- [x] `frontend/src/lib/team-lead.test.ts`
- [x] `frontend/src/components/chat/MessageList.test.tsx`
- [x] `frontend/src/lib/sse.test.ts` — Goat `persona_id: null`

---

## 4. Decyzje follow-up (P2)

1. ~~Pominąć `plan_consultation` LLM gdy `is_plan_coordination_only`~~ — zrobione (`build_plan_only_consultation`).
2. ~~Zdeprecjonować `ChatRoutingService`~~ — zrobione (`DeprecationWarning`).
3. Przywrócić fallback `get_last_responding_persona` — zrobione w `TeamLeadService`.
4. Guard idempotencji `rebuild_plan` przy retry (sprawdzenie aktywnego joba).

---

## 5. Zespół audytu

| Rola | Zakres | Wynik |
|------|--------|-------|
| Lead AI / Python | `team_lead.py`, orchestrator, tools | Pass + 8 ryzyk |
| Lead Architect | ADR-17, SSE, edge cases | Pass + drift docs |
| Lead Frontend | Etykiety, streaming, typy SSE | Pass + typy nullable |
| Documentation Architect | Plan docs, checklist | team-lead.md, ADR-17 |
