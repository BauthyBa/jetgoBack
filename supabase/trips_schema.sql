-- Trips table used by backend TripCreateView

create extension if not exists pgcrypto;

create table if not exists public.trips (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  creator_id text not null,
  origin text,
  destination text,
  date timestamptz,
  created_at timestamptz not null default now()
);

alter table public.trips enable row level security;

drop policy if exists "trips_select_creator" on public.trips;
create policy "trips_select_creator" on public.trips
  for select to authenticated
  using (creator_id = auth.uid()::text);

drop policy if exists "trips_insert_creator" on public.trips;
create policy "trips_insert_creator" on public.trips
  for insert to authenticated
  with check (creator_id = auth.uid()::text);


