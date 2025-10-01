-- Relax insert policy on chat_rooms to allow any authenticated user to create rooms

-- Ensure roles have basic privileges (idempotent in Supabase)
grant usage on schema public to anon, authenticated;
grant select, insert, update, delete on table public.chat_rooms to authenticated;

-- Replace strict insert policy with a permissive one for authenticated users
drop policy if exists "rooms_insert_creator" on public.chat_rooms;
create policy "rooms_insert_authenticated" on public.chat_rooms
  for insert
  to authenticated
  with check (true);


