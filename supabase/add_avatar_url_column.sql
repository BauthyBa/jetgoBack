-- Script para agregar columna avatar_url a la tabla User y sincronizar datos existentes

-- 1. Agregar la columna avatar_url a la tabla User
ALTER TABLE public."User" 
ADD COLUMN IF NOT EXISTS avatar_url TEXT;

-- 2. Comentario para la columna
COMMENT ON COLUMN public."User".avatar_url IS 'URL de la foto de perfil del usuario';

-- 3. Función para sincronizar avatar_url desde user_metadata
CREATE OR REPLACE FUNCTION sync_user_avatars()
RETURNS void AS $$
DECLARE
    user_record RECORD;
    avatar_url_value TEXT;
BEGIN
    -- Iterar sobre todos los usuarios en la tabla User
    FOR user_record IN 
        SELECT userid FROM public."User"
    LOOP
        -- Obtener avatar_url desde auth.users.user_metadata
        SELECT raw_user_meta_data->>'avatar_url' INTO avatar_url_value
        FROM auth.users 
        WHERE id = user_record.userid;
        
        -- Actualizar la tabla User con el avatar_url si existe
        IF avatar_url_value IS NOT NULL AND avatar_url_value != '' THEN
            UPDATE public."User" 
            SET avatar_url = avatar_url_value 
            WHERE userid = user_record.userid;
        END IF;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- 4. Ejecutar la sincronización
SELECT sync_user_avatars();

-- 5. Crear función para mantener sincronización automática
CREATE OR REPLACE FUNCTION sync_avatar_on_user_update()
RETURNS TRIGGER AS $$
BEGIN
    -- Si se actualiza user_metadata en auth.users, sincronizar con tabla User
    IF NEW.raw_user_meta_data->>'avatar_url' IS DISTINCT FROM OLD.raw_user_meta_data->>'avatar_url' THEN
        UPDATE public."User" 
        SET avatar_url = NEW.raw_user_meta_data->>'avatar_url'
        WHERE userid = NEW.id;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 6. Crear trigger para sincronización automática
DROP TRIGGER IF EXISTS sync_avatar_trigger ON auth.users;
CREATE TRIGGER sync_avatar_trigger
    AFTER UPDATE ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION sync_avatar_on_user_update();

-- 7. Limpiar función temporal
DROP FUNCTION sync_user_avatars();
