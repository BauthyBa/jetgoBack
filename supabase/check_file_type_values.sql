-- Script para verificar qué valores están permitidos en file_type
-- Ejecutar en Supabase SQL Editor

-- 1. Verificar si hay restricciones CHECK en file_type
SELECT 
    tc.constraint_name,
    tc.constraint_type,
    cc.check_clause
FROM information_schema.table_constraints tc
LEFT JOIN information_schema.check_constraints cc 
    ON tc.constraint_name = cc.constraint_name
WHERE tc.table_name = 'chat_messages' 
AND tc.table_schema = 'public'
AND tc.constraint_type = 'CHECK'
AND cc.check_clause LIKE '%file_type%';

-- 2. Verificar valores existentes en file_type
SELECT DISTINCT file_type, COUNT(*) as count
FROM public.chat_messages 
WHERE file_type IS NOT NULL
GROUP BY file_type
ORDER BY count DESC;

-- 3. Probar insertar diferentes valores
-- (Ejecutar uno por uno para ver cuál funciona)

-- Probar con 'audio/webm'
INSERT INTO public.chat_messages (
    room_id,
    user_id,
    content,
    is_file,
    file_type
) VALUES (
    '51f08343-64f0-4abe-839a-b27d9dd1d4a1',
    '0f299c7a-cf51-4f3c-aa89-01c3d8533597',
    'Test audio/webm',
    true,
    'audio/webm'
);

-- Si funciona, eliminar
DELETE FROM public.chat_messages WHERE content = 'Test audio/webm';

-- Probar con 'audio'
INSERT INTO public.chat_messages (
    room_id,
    user_id,
    content,
    is_file,
    file_type
) VALUES (
    '51f08343-64f0-4abe-839a-b27d9dd1d4a1',
    '0f299c7a-cf51-4f3c-aa89-01c3d8533597',
    'Test audio',
    true,
    'audio'
);

-- Si funciona, eliminar
DELETE FROM public.chat_messages WHERE content = 'Test audio';

-- Probar con NULL
INSERT INTO public.chat_messages (
    room_id,
    user_id,
    content,
    is_file,
    file_type
) VALUES (
    '51f08343-64f0-4abe-839a-b27d9dd1d4a1',
    '0f299c7a-cf51-4f3c-aa89-01c3d8533597',
    'Test NULL',
    true,
    NULL
);

-- Si funciona, eliminar
DELETE FROM public.chat_messages WHERE content = 'Test NULL';
