-- 0011: invoked_via — multi_slash (ADR-13 multi-reply) w CHECK constraint.
-- Uruchom w Supabase SQL Editor po 0010.

alter table public.chat_messages
  drop constraint if exists chat_messages_invoked_via_check;

alter table public.chat_messages
  add constraint chat_messages_invoked_via_check check (
    invoked_via is null
    or invoked_via in ('auto_routed', 'slash_command', 'multi_slash')
  );
