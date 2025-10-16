-- Script rápido para eliminar la validación problemática
-- Ejecutar en Supabase SQL Editor

-- Eliminar la función de validación problemática
DROP FUNCTION IF EXISTS public.validate_chat_message_file() CASCADE;

-- Eliminar cualquier trigger que use esta función
DROP TRIGGER IF EXISTS validate_chat_message_trigger ON public.chat_messages;

-- Verificar que se eliminó
SELECT 'Function removed successfully' as status;




