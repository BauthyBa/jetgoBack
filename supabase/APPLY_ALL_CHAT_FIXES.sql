-- ==========================================
-- APLICAR TODOS LOS FIXES DE CHAT Y AMIGOS
-- ==========================================
-- Este script aplica todas las correcciones necesarias para:
-- 1. Chat directo entre usuarios
-- 2. Sistema de solicitudes de amistad
-- 3. Prevenir duplicados en conversaciones

-- ==========================================
-- PASO 1: Configurar chat_members con constraint único y RLS mejorado
-- ==========================================

-- Eliminar duplicados si existen
DELETE FROM public.chat_members a
USING public.chat_members b
WHERE a.id > b.id 
AND a.room_id = b.room_id 
AND a.user_id = b.user_id;

-- Agregar constraint único si no existe
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'chat_members_room_user_unique'
    ) THEN
        ALTER TABLE public.chat_members 
        ADD CONSTRAINT chat_members_room_user_unique 
        UNIQUE (room_id, user_id);
    END IF;
END $$;

-- Actualizar políticas RLS de chat_members para permitir agregar otros usuarios
-- Esto es necesario para que el creador de la sala pueda agregar a otros miembros

DROP POLICY IF EXISTS "members_insert_self" ON public.chat_members;
DROP POLICY IF EXISTS "members_insert_self_rooms" ON public.chat_members;

-- Nueva política: permite insertar si eres el creador de la sala O si te estás agregando a ti mismo
-- Nota: Usamos CAST para manejar tanto UUID como TEXT dependiendo del schema
CREATE POLICY "members_insert_creator_or_self" ON public.chat_members
  FOR INSERT WITH CHECK (
    user_id::text = auth.uid()::text
    OR
    EXISTS (
      SELECT 1 FROM public.chat_rooms r
      WHERE r.id = chat_members.room_id 
      AND r.creator_id::text = auth.uid()::text
    )
  );

-- ==========================================
-- PASO 2: Configurar RLS para direct_conversations
-- ==========================================

-- Habilitar RLS
ALTER TABLE public.direct_conversations ENABLE ROW LEVEL SECURITY;

-- Eliminar políticas existentes
DROP POLICY IF EXISTS "direct_conv_select_participants" ON public.direct_conversations;
DROP POLICY IF EXISTS "direct_conv_insert_participant" ON public.direct_conversations;
DROP POLICY IF EXISTS "direct_conv_update_participants" ON public.direct_conversations;

-- Crear políticas
CREATE POLICY "direct_conv_select_participants" ON public.direct_conversations
  FOR SELECT USING (
    user_a = auth.uid() OR user_b = auth.uid()
  );

CREATE POLICY "direct_conv_insert_participant" ON public.direct_conversations
  FOR INSERT WITH CHECK (
    user_a = auth.uid() OR user_b = auth.uid()
  );

CREATE POLICY "direct_conv_update_participants" ON public.direct_conversations
  FOR UPDATE USING (
    user_a = auth.uid() OR user_b = auth.uid()
  );

-- Índices para direct_conversations
CREATE INDEX IF NOT EXISTS direct_conversations_user_a_idx ON public.direct_conversations(user_a);
CREATE INDEX IF NOT EXISTS direct_conversations_user_b_idx ON public.direct_conversations(user_b);
CREATE INDEX IF NOT EXISTS direct_conversations_room_id_idx ON public.direct_conversations(room_id);

-- Constraint único para evitar conversaciones duplicadas
CREATE UNIQUE INDEX IF NOT EXISTS direct_conversations_unique_pair ON public.direct_conversations(
  LEAST(user_a, user_b),
  GREATEST(user_a, user_b)
);

-- ==========================================
-- PASO 3: Configurar RLS para friend_requests
-- ==========================================

-- Habilitar RLS
ALTER TABLE public.friend_requests ENABLE ROW LEVEL SECURITY;

-- Eliminar políticas existentes
DROP POLICY IF EXISTS "friend_requests_select_involved" ON public.friend_requests;
DROP POLICY IF EXISTS "friend_requests_insert_sender" ON public.friend_requests;
DROP POLICY IF EXISTS "friend_requests_update_receiver" ON public.friend_requests;
DROP POLICY IF EXISTS "friend_requests_delete_involved" ON public.friend_requests;

-- Crear políticas
CREATE POLICY "friend_requests_select_involved" ON public.friend_requests
  FOR SELECT USING (
    sender_id = auth.uid() OR receiver_id = auth.uid()
  );

CREATE POLICY "friend_requests_insert_sender" ON public.friend_requests
  FOR INSERT WITH CHECK (
    sender_id = auth.uid()
  );

CREATE POLICY "friend_requests_update_receiver" ON public.friend_requests
  FOR UPDATE USING (
    receiver_id = auth.uid()
  ) WITH CHECK (
    receiver_id = auth.uid()
  );

CREATE POLICY "friend_requests_delete_involved" ON public.friend_requests
  FOR DELETE USING (
    sender_id = auth.uid() OR receiver_id = auth.uid()
  );

-- Índices para friend_requests
CREATE INDEX IF NOT EXISTS friend_requests_sender_idx ON public.friend_requests(sender_id);
CREATE INDEX IF NOT EXISTS friend_requests_receiver_idx ON public.friend_requests(receiver_id);
CREATE INDEX IF NOT EXISTS friend_requests_status_idx ON public.friend_requests(status);
CREATE INDEX IF NOT EXISTS friend_requests_sender_receiver_idx ON public.friend_requests(sender_id, receiver_id);

-- Constraint único para evitar solicitudes pendientes duplicadas
CREATE UNIQUE INDEX IF NOT EXISTS friend_requests_unique_pending ON public.friend_requests(
  LEAST(sender_id, receiver_id),
  GREATEST(sender_id, receiver_id)
) WHERE status = 'pending';

-- ==========================================
-- VERIFICACIÓN
-- ==========================================

-- Verificar que todas las políticas se crearon correctamente
SELECT 
    schemaname,
    tablename,
    policyname,
    permissive,
    roles,
    cmd
FROM pg_policies 
WHERE schemaname = 'public' 
AND tablename IN ('direct_conversations', 'friend_requests', 'chat_members')
ORDER BY tablename, policyname;

-- Verificar constraints
SELECT 
    conrelid::regclass AS table_name,
    conname AS constraint_name,
    contype AS constraint_type
FROM pg_constraint
WHERE conrelid IN (
    'public.chat_members'::regclass,
    'public.direct_conversations'::regclass,
    'public.friend_requests'::regclass
)
ORDER BY table_name, constraint_name;

-- Mensaje de éxito
DO $$ 
BEGIN
    RAISE NOTICE '✅ Todos los fixes se aplicaron correctamente!';
    RAISE NOTICE '✅ RLS configurado para direct_conversations';
    RAISE NOTICE '✅ RLS configurado para friend_requests';
    RAISE NOTICE '✅ Constraint único agregado a chat_members';
    RAISE NOTICE '✅ Índices creados para mejorar rendimiento';
END $$;

