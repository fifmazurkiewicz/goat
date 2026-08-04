-- Ogólna zasada granic ról: persona nie wypowiada się za inne persony (wszystkie typy).

update app_private.persona_template_safety
set safety_prompt = safety_prompt || E'\n\nZakres odpowiedzi: odpowiadasz WYŁĄCZNIE w swoim obszarze. Nie wypowiadasz się za inne persony — przy pytaniach poza zakresem wskaż właściwą rolę z zespołu użytkownika, zamiast udzielać pełnej porady z cudzego zakresu.'
where safety_prompt not like '%Nie wypowiadasz się za inne persony%';
