-- Script para verificar restricciones en chat_messages
-- Ejecutar en Supabase SQL Editor

-- 1. Verificar estructura de la tabla
SELECT 
    column_name, 
    data_type, 
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = 'chat_messages' 
AND table_schema = 'public'
ORDER BY ordinal_position;

-- 2. Verificar constraints en file_type
SELECT 
    tc.constraint_name,
    tc.constraint_type,
    cc.check_clause
FROM information_schema.table_constraints tc
LEFT JOIN information_schema.check_constraints cc 
    ON tc.constraint_name = cc.constraint_name
WHERE tc.table_name = 'chat_messages' 
AND tc.table_schema = 'public';

-- 3. Verificar si hay triggers
SELECT 
    trigger_name,
    event_manipulation,
    action_statement
FROM information_schema.triggers 
WHERE event_object_table = 'chat_messages';

-- 4. Verificar políticas RLS
SELECT 
    schemaname,
    tablename,
    policyname,
    permissive,
    roles,
    cmd,
    qual,
    with_check
FROM pg_policies 
WHERE tablename = 'chat_messages';

-- 5. Probar insertar un mensaje de prueba
INSERT INTO public.chat_messages (
    room_id,
    user_id,
    content,
    is_file,
    file_type
) VALUES (
    '51f08343-64f0-4abe-839a-b27d9dd1d4a1',
    '0f299c7a-cf51-4f3c-aa89-01c3d8533597',
    'Test audio message',
    true,
    'audio/webm'
);

-- 6. Si funciona, eliminar el registro de prueba
DELETE FROM public.chat_messages 
WHERE content = 'Test audio message';
