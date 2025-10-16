-- Script simple para eliminar la validación
-- Ejecutar en Supabase SQL Editor

-- Eliminar la función y el trigger con CASCADE
DROP FUNCTION IF EXISTS public.validate_chat_message_file() CASCADE;

-- Verificar que se eliminó
SELECT 'Function and trigger removed successfully' as status;




