-- Script para eliminar forzadamente la función y sus dependencias
-- Ejecutar en Supabase SQL Editor

-- 1. Eliminar la función con CASCADE para eliminar dependencias
DROP FUNCTION IF EXISTS public.validate_chat_message_file() CASCADE;

-- 2. Verificar que se eliminó la función
SELECT 
    routine_name,
    routine_type
FROM information_schema.routines 
WHERE routine_name = 'validate_chat_message_file'
AND routine_schema = 'public';

-- 3. Verificar que se eliminó el trigger
SELECT 
    trigger_name,
    event_manipulation,
    action_statement
FROM information_schema.triggers 
WHERE event_object_table = 'chat_messages'
AND trigger_name = 'validate_chat_message_file_trigger';

-- 4. Probar insertar un mensaje de audio
INSERT INTO public.chat_messages (
    room_id,
    user_id,
    content,
    is_file,
    file_url,
    file_name,
    file_type,
    file_size
) VALUES (
    '51f08343-64f0-4abe-839a-b27d9dd1d4a1',
    '0f299c7a-cf51-4f3c-aa89-01c3d8533597',
    'Test audio message after removal',
    true,
    'https://test.com/audio.webm',
    'test_audio.webm',
    'audio/webm',
    12345
);

-- 5. Si funciona, eliminar el registro de prueba
DELETE FROM public.chat_messages WHERE content = 'Test audio message after removal';

-- 6. Verificar que no hay más restricciones
SELECT 
    tc.constraint_name,
    tc.constraint_type,
    cc.check_clause
FROM information_schema.table_constraints tc
LEFT JOIN information_schema.check_constraints cc 
    ON tc.constraint_name = cc.constraint_name
WHERE tc.table_name = 'chat_messages' 
AND tc.table_schema = 'public';

-- 7. Verificar que no hay más triggers
SELECT 
    trigger_name,
    event_manipulation,
    action_statement
FROM information_schema.triggers 
WHERE event_object_table = 'chat_messages';
