-- Configurar RLS para notificaciones de chat
-- Este script configura las políticas de RLS para permitir que los usuarios vean mensajes de chat
-- para los cuales son miembros de la sala

-- Habilitar RLS en chat_messages si no está habilitado
ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY;

-- Política para permitir que los usuarios vean mensajes de salas donde son miembros
CREATE POLICY "Users can view messages from rooms they belong to" ON public.chat_messages
FOR SELECT
USING (
  EXISTS (
    SELECT 1 FROM public.chat_members 
    WHERE chat_members.room_id = chat_messages.room_id 
    AND chat_members.user_id = auth.uid()::text
  )
);

-- Política para permitir que los usuarios inserten mensajes en salas donde son miembros
CREATE POLICY "Users can insert messages in rooms they belong to" ON public.chat_messages
FOR INSERT
WITH CHECK (
  EXISTS (
    SELECT 1 FROM public.chat_members 
    WHERE chat_members.room_id = chat_messages.room_id 
    AND chat_members.user_id = auth.uid()::text
  )
);

-- Política para permitir que los usuarios actualicen sus propios mensajes
CREATE POLICY "Users can update their own messages" ON public.chat_messages
FOR UPDATE
USING (user_id = auth.uid()::text)
WITH CHECK (user_id = auth.uid()::text);

-- Política para permitir que los usuarios eliminen sus propios mensajes
CREATE POLICY "Users can delete their own messages" ON public.chat_messages
FOR DELETE
USING (user_id = auth.uid()::text);

-- Configurar RLS en chat_members si no está habilitado
ALTER TABLE public.chat_members ENABLE ROW LEVEL SECURITY;

-- Política para permitir que los usuarios vean miembros de salas donde pertenecen
CREATE POLICY "Users can view members of rooms they belong to" ON public.chat_members
FOR SELECT
USING (
  EXISTS (
    SELECT 1 FROM public.chat_members cm 
    WHERE cm.room_id = chat_members.room_id 
    AND cm.user_id = auth.uid()::text
  )
);

-- Política para permitir que los usuarios se unan a salas
CREATE POLICY "Users can join rooms" ON public.chat_members
FOR INSERT
WITH CHECK (user_id = auth.uid()::text);

-- Política para permitir que los usuarios abandonen salas
CREATE POLICY "Users can leave rooms" ON public.chat_members
FOR DELETE
USING (user_id = auth.uid()::text);

-- Configurar RLS en chat_rooms si no está habilitado
ALTER TABLE public.chat_rooms ENABLE ROW LEVEL SECURITY;

-- Política para permitir que los usuarios vean salas donde son miembros
CREATE POLICY "Users can view rooms they belong to" ON public.chat_rooms
FOR SELECT
USING (
  EXISTS (
    SELECT 1 FROM public.chat_members 
    WHERE chat_members.room_id = chat_rooms.id 
    AND chat_members.user_id = auth.uid()::text
  )
);

-- Política para permitir que los usuarios creen salas
CREATE POLICY "Users can create rooms" ON public.chat_rooms
FOR INSERT
WITH CHECK (true);

-- Política para permitir que los usuarios actualicen salas que crearon
CREATE POLICY "Users can update rooms they created" ON public.chat_rooms
FOR UPDATE
USING (creator_id = auth.uid()::text)
WITH CHECK (creator_id = auth.uid()::text);

-- Política para permitir que los usuarios eliminen salas que crearon
CREATE POLICY "Users can delete rooms they created" ON public.chat_rooms
FOR DELETE
USING (creator_id = auth.uid()::text);
