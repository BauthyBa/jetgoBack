-- Script para arreglar la tabla chat_messages
-- Ejecutar en Supabase SQL Editor

-- 1. Verificar si hay restricciones en file_type
SELECT 
    tc.constraint_name,
    tc.constraint_type,
    cc.check_clause
FROM information_schema.table_constraints tc
LEFT JOIN information_schema.check_constraints cc 
    ON tc.constraint_name = cc.constraint_name
WHERE tc.table_name = 'chat_messages' 
AND tc.table_schema = 'public'
AND tc.constraint_type = 'CHECK';

-- 2. Si hay restricciones, eliminarlas
-- (Ejecutar solo si el paso 1 muestra restricciones)
-- ALTER TABLE public.chat_messages DROP CONSTRAINT [nombre_de_la_restriccion];

-- 3. Verificar políticas RLS que puedan estar bloqueando
SELECT 
    policyname,
    cmd,
    qual,
    with_check
FROM pg_policies 
WHERE tablename = 'chat_messages';

-- 4. Si hay políticas restrictivas, eliminarlas temporalmente
-- (Ejecutar solo si el paso 3 muestra políticas problemáticas)
-- DROP POLICY [nombre_de_la_politica] ON public.chat_messages;

-- 5. Crear política RLS permisiva para chat_messages
CREATE POLICY "Allow authenticated users to insert chat messages" 
ON public.chat_messages 
FOR INSERT 
TO authenticated 
WITH CHECK (true);

CREATE POLICY "Allow authenticated users to select chat messages" 
ON public.chat_messages 
FOR SELECT 
TO authenticated 
USING (true);

-- 6. Habilitar RLS en la tabla si no está habilitado
ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY;

-- 7. Verificar que la tabla permite audio/webm
SELECT 
    column_name, 
    data_type, 
    is_nullable
FROM information_schema.columns 
WHERE table_name = 'chat_messages' 
AND column_name = 'file_type';
