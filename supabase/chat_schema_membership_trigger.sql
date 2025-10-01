-- Automatically add creator as owner member when a room is created

create or replace function public.fn_chat_rooms_after_insert()
returns trigger
language plpgsql
as $$
begin
  begin
    insert into public.chat_members(room_id, user_id, role)
    values (NEW.id, NEW.creator_id, 'owner')
    on conflict (room_id, user_id) do nothing;
  exception when others then
    -- swallow to avoid breaking room creation
    null;
  end;
  return NEW;
end;
$$;

drop trigger if exists trg_chat_rooms_after_insert on public.chat_rooms;
create trigger trg_chat_rooms_after_insert
after insert on public.chat_rooms
for each row execute function public.fn_chat_rooms_after_insert();


