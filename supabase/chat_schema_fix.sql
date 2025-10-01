-- Quick fix for missing columns / policies in chat tables
-- Run this in Supabase SQL editor if you get errors like: column "user_id" does not exist

-- Create extension for uuid if needed
create extension if not exists pgcrypto;

-- Ensure tables exist (no-op if already created by previous script)
create table if not exists public.chat_rooms (
  id uuid primary key default gen_random_uuid(),
  name text,
  creator_id text,
  created_at timestamptz not null default now()
);

create table if not exists public.chat_members (
  id uuid primary key default gen_random_uuid(),
  room_id uuid references public.chat_rooms(id) on delete cascade,
  user_id text,
  role text,
  created_at timestamptz not null default now()
);

create table if not exists public.chat_messages (
  id uuid primary key default gen_random_uuid(),
  room_id uuid references public.chat_rooms(id) on delete cascade,
  user_id text,
  content text,
  created_at timestamptz not null default now()
);

create table if not exists public.chat_invitations (
  id uuid primary key default gen_random_uuid(),
  room_id uuid,
  email text,
  inviter_id text,
  status text,
  created_at timestamptz not null default now()
);

-- Add missing columns safely
alter table public.chat_rooms     add column if not exists creator_id text;
alter table public.chat_rooms     add column if not exists name text;
alter table public.chat_members   add column if not exists user_id text;
alter table public.chat_members   add column if not exists role text;
alter table public.chat_members   add column if not exists room_id uuid;
alter table public.chat_messages  add column if not exists user_id text;
alter table public.chat_messages  add column if not exists room_id uuid;
alter table public.chat_messages  add column if not exists content text;
alter table public.chat_invitations add column if not exists inviter_id text;

-- Indexes
create index if not exists chat_messages_room_created_at_idx on public.chat_messages(room_id, created_at);
create index if not exists chat_members_room_user_idx on public.chat_members(room_id, user_id);

-- Enable RLS
alter table public.chat_rooms enable row level security;
alter table public.chat_members enable row level security;
alter table public.chat_messages enable row level security;
alter table public.chat_invitations enable row level security;

-- Recreate policies to reference correct columns
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

drop policy if exists "inv_select_self_related" on public.chat_invitations;
create policy "inv_select_self_related" on public.chat_invitations
  for select using (
    inviter_id = auth.uid()::text or email = auth.jwt() ->> 'email'
  );

drop policy if exists "inv_insert_self" on public.chat_invitations;
create policy "inv_insert_self" on public.chat_invitations
  for insert with check (
    inviter_id = auth.uid()::text
  );

-- Realtime: ensure messages table is published
do $$
begin
  if not exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
    create publication supabase_realtime;
  end if;
end
$$;

alter publication supabase_realtime add table public.chat_messages;


