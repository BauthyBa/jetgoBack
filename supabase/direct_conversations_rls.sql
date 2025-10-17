-- Configurar RLS para direct_conversations
-- Este archivo configura las políticas de seguridad a nivel de fila para la tabla direct_conversations

-- Habilitar RLS si no está habilitado
ALTER TABLE public.direct_conversations ENABLE ROW LEVEL SECURITY;

-- Política de SELECT: Los usuarios pueden ver conversaciones donde son participantes (user_a o user_b)
DROP POLICY IF EXISTS "direct_conv_select_participants" ON public.direct_conversations;
CREATE POLICY "direct_conv_select_participants" ON public.direct_conversations
  FOR SELECT USING (
    user_a = auth.uid() OR user_b = auth.uid()
  );

-- Política de INSERT: Los usuarios pueden crear conversaciones donde ellos son uno de los participantes
DROP POLICY IF EXISTS "direct_conv_insert_participant" ON public.direct_conversations;
CREATE POLICY "direct_conv_insert_participant" ON public.direct_conversations
  FOR INSERT WITH CHECK (
    user_a = auth.uid() OR user_b = auth.uid()
  );

-- Política de UPDATE: Los usuarios pueden actualizar conversaciones donde son participantes
DROP POLICY IF EXISTS "direct_conv_update_participants" ON public.direct_conversations;
CREATE POLICY "direct_conv_update_participants" ON public.direct_conversations
  FOR UPDATE USING (
    user_a = auth.uid() OR user_b = auth.uid()
  );

-- Índices para mejorar el rendimiento de las consultas
CREATE INDEX IF NOT EXISTS direct_conversations_user_a_idx ON public.direct_conversations(user_a);
CREATE INDEX IF NOT EXISTS direct_conversations_user_b_idx ON public.direct_conversations(user_b);
CREATE INDEX IF NOT EXISTS direct_conversations_room_id_idx ON public.direct_conversations(room_id);

-- Constraint para evitar conversaciones duplicadas
-- Asegura que no haya múltiples conversaciones entre los mismos usuarios
CREATE UNIQUE INDEX IF NOT EXISTS direct_conversations_unique_pair ON public.direct_conversations(
  LEAST(user_a, user_b),
  GREATEST(user_a, user_b)
);

