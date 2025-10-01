-- Add trip_id to chat_rooms to link chat with a trip

alter table public.chat_rooms add column if not exists trip_id uuid;
create index if not exists chat_rooms_trip_idx on public.chat_rooms(trip_id);


