-- Script para eliminar la función de validación problemática
-- Ejecutar en Supabase SQL Editor

-- 1. Verificar la función actual
SELECT 
    routine_name,
    routine_type,
    routine_definition
FROM information_schema.routines 
WHERE routine_name = 'validate_chat_message_file'
AND routine_schema = 'public';

-- 2. Verificar triggers que usan esta función
SELECT 
    trigger_name,
    event_manipulation,
    action_statement,
    action_timing
FROM information_schema.triggers 
WHERE event_object_table = 'chat_messages'
AND action_statement LIKE '%validate_chat_message_file%';

-- 3. Eliminar triggers que usan la función
-- (Ejecutar solo si el paso 2 muestra triggers)
DROP TRIGGER IF EXISTS validate_chat_message_trigger ON public.chat_messages;

-- 4. Eliminar la función problemática
DROP FUNCTION IF EXISTS public.validate_chat_message_file();

-- 5. Verificar que se eliminó
SELECT 
    routine_name,
    routine_type
FROM information_schema.routines 
WHERE routine_name = 'validate_chat_message_file'
AND routine_schema = 'public';

-- 6. Probar insertar un mensaje de audio
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
    'Test audio message',
    true,
    'https://test.com/audio.webm',
    'test_audio.webm',
    'audio/webm',
    12345
);

-- 7. Si funciona, eliminar el registro de prueba
DELETE FROM public.chat_messages WHERE content = 'Test audio message';

-- 8. Verificar que no hay más restricciones
SELECT 
    tc.constraint_name,
    tc.constraint_type,
    cc.check_clause
FROM information_schema.table_constraints tc
LEFT JOIN information_schema.check_constraints cc 
    ON tc.constraint_name = cc.constraint_name
WHERE tc.table_name = 'chat_messages' 
AND tc.table_schema = 'public';
