-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.User (
  userid uuid NOT NULL,
  dni text,
  nombre text,
  apellido text,
  mail text,
  estuserid integer,
  sexo text,
  fecha_nacimiento date,
  mail_confirmacion boolean DEFAULT false,
  created_at timestamp without time zone DEFAULT now(),
  CONSTRAINT User_pkey PRIMARY KEY (userid),
  CONSTRAINT User_userid_fkey FOREIGN KEY (userid) REFERENCES auth.users(id)
);
CREATE TABLE public.chat_members (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  room_id uuid NOT NULL,
  user_id uuid NOT NULL,
  role text NOT NULL DEFAULT 'member'::text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT chat_members_pkey PRIMARY KEY (id),
  CONSTRAINT chat_members_room_id_fkey FOREIGN KEY (room_id) REFERENCES public.chat_rooms(id),
  CONSTRAINT chat_members_user_fk FOREIGN KEY (user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.chat_messages (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  room_id uuid NOT NULL,
  user_id uuid NOT NULL,
  content text NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT chat_messages_pkey PRIMARY KEY (id),
  CONSTRAINT chat_messages_room_id_fkey FOREIGN KEY (room_id) REFERENCES public.chat_rooms(id),
  CONSTRAINT chat_messages_user_fk FOREIGN KEY (user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.chat_rooms (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  name text NOT NULL,
  creator_id uuid NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  trip_id uuid,
  CONSTRAINT chat_rooms_pkey PRIMARY KEY (id),
  CONSTRAINT chat_rooms_creator_fk FOREIGN KEY (creator_id) REFERENCES auth.users(id),
  CONSTRAINT chat_rooms_trip_fk FOREIGN KEY (trip_id) REFERENCES public.trips(id)
);
CREATE TABLE public.trip_members (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  trip_id uuid NOT NULL,
  user_id uuid NOT NULL,
  role text NOT NULL DEFAULT 'member'::text,
  joined_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT trip_members_pkey PRIMARY KEY (id),
  CONSTRAINT trip_members_user_fk FOREIGN KEY (user_id) REFERENCES auth.users(id),
  CONSTRAINT trip_members_trip_id_fkey FOREIGN KEY (trip_id) REFERENCES public.trips(id)
);
CREATE TABLE public.trips (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  name text NOT NULL,
  creator_id uuid NOT NULL,
  origin text,
  destination text,
  start_date timestamp with time zone,
  end_date timestamp with time zone,
  budget_min numeric,
  budget_max numeric,
  status text,
  room_type text,
  season text,
  country text,
  date timestamp with time zone,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT trips_pkey PRIMARY KEY (id),
  CONSTRAINT trips_creator_fk FOREIGN KEY (creator_id) REFERENCES auth.users(id)
);