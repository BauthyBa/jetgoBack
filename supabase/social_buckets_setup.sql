-- =====================================================
-- CONFIGURACIÓN DE BUCKETS PARA SISTEMA SOCIAL
-- =====================================================
-- Este archivo contiene la configuración de buckets de Supabase
-- para almacenar imágenes y videos de posts y stories

-- =====================================================
-- 1. CREAR BUCKET PARA POSTS
-- =====================================================

-- Crear bucket para posts (imágenes y videos de publicaciones)
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'jetgo-posts',
    'jetgo-posts',
    true,
    52428800, -- 50MB límite
    ARRAY[
        'image/jpeg',
        'image/jpg', 
        'image/png',
        'image/gif',
        'image/webp',
        'video/mp4',
        'video/webm',
        'video/quicktime',
        'video/x-msvideo'
    ]
);

-- =====================================================
-- 2. CREAR BUCKET PARA STORIES
-- =====================================================

-- Crear bucket para stories (imágenes y videos de historias)
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'jetgo-stories',
    'jetgo-stories', 
    true,
    104857600, -- 100MB límite (más grande para videos)
    ARRAY[
        'image/jpeg',
        'image/jpg',
        'image/png', 
        'image/gif',
        'image/webp',
        'video/mp4',
        'video/webm',
        'video/quicktime',
        'video/x-msvideo'
    ]
);

-- =====================================================
-- 3. POLÍTICAS DE STORAGE PARA POSTS
-- =====================================================

-- Política: Cualquiera puede ver archivos públicos de posts
CREATE POLICY "Public posts are viewable by everyone" ON storage.objects
    FOR SELECT USING (bucket_id = 'jetgo-posts');

-- Política: Usuarios autenticados pueden subir archivos a posts
CREATE POLICY "Authenticated users can upload posts" ON storage.objects
    FOR INSERT WITH CHECK (
        bucket_id = 'jetgo-posts' 
        AND auth.role() = 'authenticated'
    );

-- Política: Usuarios pueden actualizar sus propios archivos de posts
CREATE POLICY "Users can update their own posts" ON storage.objects
    FOR UPDATE USING (
        bucket_id = 'jetgo-posts' 
        AND auth.uid()::text = (storage.foldername(name))[1]
    );

-- Política: Usuarios pueden eliminar sus propios archivos de posts
CREATE POLICY "Users can delete their own posts" ON storage.objects
    FOR DELETE USING (
        bucket_id = 'jetgo-posts' 
        AND auth.uid()::text = (storage.foldername(name))[1]
    );

-- =====================================================
-- 4. POLÍTICAS DE STORAGE PARA STORIES
-- =====================================================

-- Política: Cualquiera puede ver archivos públicos de stories
CREATE POLICY "Public stories are viewable by everyone" ON storage.objects
    FOR SELECT USING (bucket_id = 'jetgo-stories');

-- Política: Usuarios autenticados pueden subir archivos a stories
CREATE POLICY "Authenticated users can upload stories" ON storage.objects
    FOR INSERT WITH CHECK (
        bucket_id = 'jetgo-stories' 
        AND auth.role() = 'authenticated'
    );

-- Política: Usuarios pueden actualizar sus propios archivos de stories
CREATE POLICY "Users can update their own stories" ON storage.objects
    FOR UPDATE USING (
        bucket_id = 'jetgo-stories' 
        AND auth.uid()::text = (storage.foldername(name))[1]
    );

-- Política: Usuarios pueden eliminar sus propios archivos de stories
CREATE POLICY "Users can delete their own stories" ON storage.objects
    FOR DELETE USING (
        bucket_id = 'jetgo-stories' 
        AND auth.uid()::text = (storage.foldername(name))[1]
    );

-- =====================================================
-- 5. FUNCIÓN PARA LIMPIAR STORIES EXPIRADAS
-- =====================================================

-- Función para eliminar archivos de stories expiradas del storage
CREATE OR REPLACE FUNCTION cleanup_expired_story_files()
RETURNS void AS $$
DECLARE
    expired_story RECORD;
BEGIN
    -- Obtener stories expiradas
    FOR expired_story IN 
        SELECT id, user_id, media_url 
        FROM public.stories 
        WHERE expires_at < NOW() 
        AND is_archived = false
    LOOP
        -- Extraer el path del archivo de la URL
        DECLARE
            file_path text;
        BEGIN
            -- Extraer path del archivo de la URL
            file_path := regexp_replace(expired_story.media_url, '.*jetgo-stories/', '');
            
            -- Eliminar archivo del storage
            PERFORM storage.delete_object('jetgo-stories', file_path);
            
            -- Marcar story como archivada
            UPDATE public.stories 
            SET is_archived = true 
            WHERE id = expired_story.id;
            
        EXCEPTION WHEN OTHERS THEN
            -- Log error pero continuar
            RAISE WARNING 'Error deleting story file %: %', expired_story.media_url, SQLERRM;
        END;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 6. FUNCIÓN PARA OBTENER URL DE ARCHIVO
-- =====================================================

-- Función helper para generar URLs de archivos
CREATE OR REPLACE FUNCTION get_storage_url(bucket_name text, file_path text)
RETURNS text AS $$
BEGIN
    RETURN 'https://' || current_setting('app.settings.supabase_url') || '/storage/v1/object/public/' || bucket_name || '/' || file_path;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 7. TRIGGER PARA LIMPIEZA AUTOMÁTICA DE STORIES
-- =====================================================

-- Función que se ejecuta cada hora para limpiar stories expiradas
CREATE OR REPLACE FUNCTION schedule_story_cleanup()
RETURNS void AS $$
BEGIN
    -- Limpiar stories expiradas de la base de datos
    PERFORM cleanup_expired_stories();
    
    -- Limpiar archivos de stories expiradas del storage
    PERFORM cleanup_expired_story_files();
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 8. CONFIGURACIÓN DE CRON JOB (OPCIONAL)
-- =====================================================

-- Nota: Para configurar limpieza automática cada hora, 
-- necesitarás configurar un cron job en tu servidor o usar
-- pg_cron si está disponible en tu instancia de Supabase

-- Ejemplo de configuración de pg_cron (si está disponible):
-- SELECT cron.schedule('cleanup-stories', '0 * * * *', 'SELECT cleanup_expired_stories();');
-- SELECT cron.schedule('cleanup-story-files', '0 * * * *', 'SELECT cleanup_expired_story_files();');

-- =====================================================
-- 9. FUNCIONES HELPER PARA EL FRONTEND
-- =====================================================

-- Función para subir archivo a posts
CREATE OR REPLACE FUNCTION upload_post_file(
    file_name text,
    file_content bytea,
    content_type text
)
RETURNS text AS $$
DECLARE
    file_path text;
    file_url text;
BEGIN
    -- Generar path único
    file_path := auth.uid()::text || '/' || extract(epoch from now())::text || '_' || file_name;
    
    -- Subir archivo al bucket
    PERFORM storage.upload_file(
        'jetgo-posts',
        file_path,
        file_content,
        content_type
    );
    
    -- Generar URL pública
    file_url := get_storage_url('jetgo-posts', file_path);
    
    RETURN file_url;
END;
$$ LANGUAGE plpgsql;

-- Función para subir archivo a stories
CREATE OR REPLACE FUNCTION upload_story_file(
    file_name text,
    file_content bytea,
    content_type text
)
RETURNS text AS $$
DECLARE
    file_path text;
    file_url text;
BEGIN
    -- Generar path único
    file_path := auth.uid()::text || '/' || extract(epoch from now())::text || '_' || file_name;
    
    -- Subir archivo al bucket
    PERFORM storage.upload_file(
        'jetgo-stories',
        file_path,
        file_content,
        content_type
    );
    
    -- Generar URL pública
    file_url := get_storage_url('jetgo-stories', file_path);
    
    RETURN file_url;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- COMENTARIOS FINALES
-- =====================================================

-- Este archivo configura:
-- ✅ Bucket para posts (50MB límite)
-- ✅ Bucket para stories (100MB límite) 
-- ✅ Políticas de seguridad para storage
-- ✅ Funciones de limpieza automática
-- ✅ Funciones helper para subir archivos
-- ✅ Soporte para imágenes y videos

-- Tipos de archivo soportados:
-- 📸 Imágenes: JPEG, PNG, GIF, WebP
-- 🎥 Videos: MP4, WebM, QuickTime, AVI

-- Próximos pasos:
-- 1. Ejecutar este SQL en Supabase
-- 2. Verificar que los buckets se crearon correctamente
-- 3. Configurar cron job para limpieza automática
-- 4. Implementar frontend del sistema social
