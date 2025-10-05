-- Trips schema full reset: drop and recreate tables and RLS policies

create extension if not exists pgcrypto;

-- Drop existing policies first to avoid dependency issues
do $$
begin
  if exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'trips') then
    drop policy if exists "trips_select_access" on public.trips;
    drop policy if exists "trips_insert_creator" on public.trips;
    drop policy if exists "trips_update_creator" on public.trips;
    drop policy if exists "trips_delete_creator" on public.trips;
  end if;
  if exists (select 1 from information_schema.tables where table_schema='public' and table_name='trip_members') then
    drop policy if exists "trip_members_select_self" on public.trip_members;
    drop policy if exists "trip_members_insert_self" on public.trip_members;
    drop policy if exists "trip_members_delete_self" on public.trip_members;
  end if;
exception when others then
  null;
end$$;

-- Drop tables (cascade members first)
drop table if exists public.trip_members cascade;
drop table if exists public.trips cascade;

-- Recreate trips with full columns used by frontend filters and backend
create table public.trips (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  creator_id text not null, -- Supabase auth.uid() stored as text
  origin text,
  destination text,
  image_url text,
  start_date timestamptz,
  end_date timestamptz,
  budget_min numeric,
  budget_max numeric,
  status text,
  room_type text,
  season text,
  country text,
  date timestamptz, -- legacy compatibility
  created_at timestamptz not null default now()
);

-- Join table between trips and users (participants)
create table public.trip_members (
  id uuid primary key default gen_random_uuid(),
  trip_id uuid not null references public.trips(id) on delete cascade,
  user_id text not null, -- Supabase auth.uid() as text
  role text not null default 'member', -- member | owner
  joined_at timestamptz not null default now(),
  unique (trip_id, user_id)
);

-- Indexes
create index if not exists idx_trips_creator on public.trips(creator_id);
create index if not exists idx_trips_dates on public.trips(start_date, end_date);
-- Unique trip name (case-insensitive)
do $$
begin
  if not exists (
    select 1 from pg_indexes where schemaname = 'public' and indexname = 'ux_trips_name_ci'
  ) then
    execute 'create unique index ux_trips_name_ci on public.trips (lower(name))';
  end if;
exception when others then null; end$$;
create index if not exists idx_trip_members_trip on public.trip_members(trip_id);
create index if not exists idx_trip_members_user on public.trip_members(user_id);

-- RLS
alter table public.trips enable row level security;
alter table public.trip_members enable row level security;

-- Allow authenticated users to see trips they created OR where they are participants
drop policy if exists "trips_select_access" on public.trips;
create policy "trips_select_access" on public.trips
  for select to authenticated
  using (
    creator_id = auth.uid()::text
    or exists (
      select 1 from public.trip_members tm
      where tm.trip_id = trips.id and tm.user_id = auth.uid()::text
    )
  );

-- Only allow inserts where creator_id matches current user
drop policy if exists "trips_insert_creator" on public.trips;
create policy "trips_insert_creator" on public.trips
  for insert to authenticated
  with check (creator_id = auth.uid()::text);

-- Allow creators to update/delete their trips (optional; keep strict)
drop policy if exists "trips_update_creator" on public.trips;
create policy "trips_update_creator" on public.trips
  for update to authenticated
  using (creator_id = auth.uid()::text)
  with check (creator_id = auth.uid()::text);

drop policy if exists "trips_delete_creator" on public.trips;
create policy "trips_delete_creator" on public.trips
  for delete to authenticated
  using (creator_id = auth.uid()::text);

-- trip_members: users can see their memberships
drop policy if exists "trip_members_select_self" on public.trip_members;
create policy "trip_members_select_self" on public.trip_members
  for select to authenticated
  using (user_id = auth.uid()::text);

-- Allow users to insert their own membership (creator can later manage via RPC if needed)
drop policy if exists "trip_members_insert_self" on public.trip_members;
create policy "trip_members_insert_self" on public.trip_members
  for insert to authenticated
  with check (user_id = auth.uid()::text);

-- Allow users to leave a trip (delete their membership)
drop policy if exists "trip_members_delete_self" on public.trip_members;
create policy "trip_members_delete_self" on public.trip_members
  for delete to authenticated
  using (user_id = auth.uid()::text);


