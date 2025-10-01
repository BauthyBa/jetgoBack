-- Enable UUID generator
create extension if not exists pgcrypto;

-- Tables
create table if not exists public.chat_rooms (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  creator_id text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.chat_members (
  id uuid primary key default gen_random_uuid(),
  room_id uuid not null references public.chat_rooms(id) on delete cascade,
  user_id text not null,
  role text not null default 'member',
  created_at timestamptz not null default now(),
  unique (room_id, user_id)
);

create table if not exists public.chat_messages (
  id uuid primary key default gen_random_uuid(),
  room_id uuid not null references public.chat_rooms(id) on delete cascade,
  user_id text not null,
  content text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.chat_invitations (
  id uuid primary key default gen_random_uuid(),
  room_id uuid not null,
  email text not null,
  inviter_id text,
  status text not null default 'sent',
  created_at timestamptz not null default now()
);

-- Indexes
create index if not exists chat_messages_room_created_at_idx on public.chat_messages(room_id, created_at);
create index if not exists chat_members_room_user_idx on public.chat_members(room_id, user_id);

-- RLS
alter table public.chat_rooms enable row level security;
alter table public.chat_members enable row level security;
alter table public.chat_messages enable row level security;
alter table public.chat_invitations enable row level security;

-- Policies: Chat rooms
drop policy if exists "rooms_select_members" on public.chat_rooms;
create policy "rooms_select_members" on public.chat_rooms
  for select using (
    exists (
      select 1 from public.chat_members m
      where m.room_id = chat_rooms.id and m.user_id = auth.uid()::text
    )
  );

drop policy if exists "rooms_insert_creator" on public.chat_rooms;
create policy "rooms_insert_creator" on public.chat_rooms
  for insert with check (
    creator_id = auth.uid()::text
  );

-- Policies: Chat members
drop policy if exists "members_select_self_rooms" on public.chat_members;
create policy "members_select_self_rooms" on public.chat_members
  for select using (
    user_id = auth.uid()::text
  );

drop policy if exists "members_insert_self" on public.chat_members;
create policy "members_insert_self" on public.chat_members
  for insert with check (
    user_id = auth.uid()::text
  );

-- Policies: Chat messages
drop policy if exists "messages_select_members" on public.chat_messages;
create policy "messages_select_members" on public.chat_messages
  for select using (
    exists (
      select 1 from public.chat_members m
      where m.room_id = chat_messages.room_id and m.user_id = auth.uid()::text
    )
  );

drop policy if exists "messages_insert_members" on public.chat_messages;
create policy "messages_insert_members" on public.chat_messages
  for insert with check (
    exists (
      select 1 from public.chat_members m
      where m.room_id = chat_messages.room_id and m.user_id = auth.uid()::text
    ) and user_id = auth.uid()::text
  );

-- Invitations: allow user to see invitations they sent or received
drop policy if exists "inv_select_self_related" on public.chat_invitations;
create policy "inv_select_self_related" on public.chat_invitations
  for select using (
    inviter_id = auth.uid()::text
    or email = auth.jwt() ->> 'email'
  );

drop policy if exists "inv_insert_self" on public.chat_invitations;
create policy "inv_insert_self" on public.chat_invitations
  for insert with check (
    inviter_id = auth.uid()::text
  );

-- Realtime publication
-- Ensure the publication exists and add the messages table
do $$
begin
  if not exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
    create publication supabase_realtime;
  end if;
end
$$;

alter publication supabase_realtime add table public.chat_messages;


