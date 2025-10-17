-- Agregar constraint único para chat_members
-- Esto evita que un usuario sea agregado múltiples veces a la misma sala

-- Verificar si el constraint ya existe antes de crearlo
DO $$ 
BEGIN
    -- Intentar crear el índice único si no existe
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'chat_members_room_user_unique'
    ) THEN
        -- Primero, eliminar duplicados si existen
        DELETE FROM public.chat_members a
        USING public.chat_members b
        WHERE a.id > b.id 
        AND a.room_id = b.room_id 
        AND a.user_id = b.user_id;
        
        -- Crear el constraint único
        ALTER TABLE public.chat_members 
        ADD CONSTRAINT chat_members_room_user_unique 
        UNIQUE (room_id, user_id);
        
        RAISE NOTICE 'Constraint único creado exitosamente para chat_members';
    ELSE
        RAISE NOTICE 'El constraint único ya existe para chat_members';
    END IF;
END $$;

-- Verificar que el constraint existe
SELECT 
    conname AS constraint_name,
    contype AS constraint_type
FROM pg_constraint
WHERE conrelid = 'public.chat_members'::regclass
AND conname = 'chat_members_room_user_unique';

