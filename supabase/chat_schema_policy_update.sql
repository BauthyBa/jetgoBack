-- Allow creators to SELECT their rooms immediately after INSERT

-- Replace the previous select policy with a creator-or-member check
drop policy if exists "rooms_select_members" on public.chat_rooms;
create policy "rooms_select_creator_or_member" on public.chat_rooms
  for select
  to authenticated
  using (
    creator_id = auth.uid()::text
    or exists (
      select 1 from public.chat_members m
      where m.room_id = chat_rooms.id and m.user_id = auth.uid()::text
    )
  );


