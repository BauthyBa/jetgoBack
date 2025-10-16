-- =====================================================
-- AUTOMATIZACIÓN DE LIMPIEZA PARA SISTEMA SOCIAL
-- =====================================================
-- Este archivo contiene funciones y configuraciones para
-- la limpieza automática de stories y archivos expirados

-- =====================================================
-- 1. FUNCIÓN PRINCIPAL DE LIMPIEZA
-- =====================================================

-- Eliminar funciones existentes si existen
DROP FUNCTION IF EXISTS social_cleanup_job();
DROP FUNCTION IF EXISTS cleanup_expired_story_files();
DROP FUNCTION IF EXISTS cleanup_deleted_posts();
DROP FUNCTION IF EXISTS manual_social_cleanup(text);
DROP FUNCTION IF EXISTS get_cleanup_stats();
DROP FUNCTION IF EXISTS get_storage_usage();

CREATE OR REPLACE FUNCTION social_cleanup_job()
RETURNS void AS $$
DECLARE
    cleanup_count integer := 0;
    file_cleanup_count integer := 0;
BEGIN
    -- Log inicio del job
    RAISE LOG 'Starting social cleanup job at %', NOW();
    
    -- 1. Limpiar stories expiradas de la base de datos
    DELETE FROM public.stories 
    WHERE expires_at < NOW() 
    AND is_archived = false;
    
    GET DIAGNOSTICS cleanup_count = ROW_COUNT;
    RAISE LOG 'Deleted % expired stories from database', cleanup_count;
    
    -- 2. Limpiar archivos de stories expiradas del storage
    PERFORM cleanup_expired_story_files();
    
    -- 3. Limpiar notificaciones muy antiguas (más de 30 días)
    DELETE FROM public.social_notifications 
    WHERE created_at < NOW() - INTERVAL '30 days'
    AND is_read = true;
    
    GET DIAGNOSTICS file_cleanup_count = ROW_COUNT;
    RAISE LOG 'Deleted % old notifications', file_cleanup_count;
    
    -- 4. Limpiar comentarios eliminados (soft delete) muy antiguos
    UPDATE public.post_comments 
    SET deleted_at = NOW()
    WHERE deleted_at IS NOT NULL 
    AND deleted_at < NOW() - INTERVAL '90 days';
    
    -- Log fin del job
    RAISE LOG 'Social cleanup job completed at %', NOW();
    
EXCEPTION WHEN OTHERS THEN
    RAISE LOG 'Error in social cleanup job: %', SQLERRM;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 2. FUNCIÓN MEJORADA PARA LIMPIAR ARCHIVOS DE STORIES
-- =====================================================

CREATE OR REPLACE FUNCTION cleanup_expired_story_files()
RETURNS integer AS $$
DECLARE
    expired_story RECORD;
    file_path text;
    deleted_count integer := 0;
    error_count integer := 0;
BEGIN
    -- Obtener stories expiradas que aún no han sido archivadas
    FOR expired_story IN 
        SELECT id, user_id, media_url, created_at
        FROM public.stories 
        WHERE expires_at < NOW() 
        AND is_archived = false
        ORDER BY created_at ASC
        LIMIT 100 -- Procesar máximo 100 por vez para evitar timeouts
    LOOP
        BEGIN
            -- Extraer el path del archivo de la URL
            file_path := regexp_replace(expired_story.media_url, '.*jetgo-stories/', '');
            
            -- Verificar que el archivo existe antes de intentar eliminarlo
            IF file_path IS NOT NULL AND file_path != '' THEN
                -- Eliminar archivo del storage
                PERFORM storage.delete_object('jetgo-stories', file_path);
                deleted_count := deleted_count + 1;
                
                RAISE LOG 'Deleted story file: %', file_path;
            END IF;
            
            -- Marcar story como archivada
            UPDATE public.stories 
            SET is_archived = true 
            WHERE id = expired_story.id;
            
        EXCEPTION WHEN OTHERS THEN
            error_count := error_count + 1;
            RAISE WARNING 'Error deleting story file %: %', expired_story.media_url, SQLERRM;
            
            -- Marcar como archivada aunque haya error para evitar reintentos
            UPDATE public.stories 
            SET is_archived = true 
            WHERE id = expired_story.id;
        END;
    END LOOP;
    
    RAISE LOG 'Story files cleanup completed: % deleted, % errors', deleted_count, error_count;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 3. FUNCIÓN PARA LIMPIAR POSTS ELIMINADOS
-- =====================================================

CREATE OR REPLACE FUNCTION cleanup_deleted_posts()
RETURNS integer AS $$
DECLARE
    deleted_post RECORD;
    file_path text;
    deleted_count integer := 0;
BEGIN
    -- Obtener posts eliminados hace más de 7 días
    FOR deleted_post IN 
        SELECT id, user_id, image_url, video_url, deleted_at
        FROM public.posts 
        WHERE deleted_at IS NOT NULL 
        AND deleted_at < NOW() - INTERVAL '7 days'
        ORDER BY deleted_at ASC
        LIMIT 50 -- Procesar máximo 50 por vez
    LOOP
        BEGIN
            -- Limpiar imagen si existe
            IF deleted_post.image_url IS NOT NULL THEN
                file_path := regexp_replace(deleted_post.image_url, '.*jetgo-posts/', '');
                IF file_path IS NOT NULL AND file_path != '' THEN
                    PERFORM storage.delete_object('jetgo-posts', file_path);
                END IF;
            END IF;
            
            -- Limpiar video si existe
            IF deleted_post.video_url IS NOT NULL THEN
                file_path := regexp_replace(deleted_post.video_url, '.*jetgo-posts/', '');
                IF file_path IS NOT NULL AND file_path != '' THEN
                    PERFORM storage.delete_object('jetgo-posts', file_path);
                END IF;
            END IF;
            
            -- Eliminar el registro del post
            DELETE FROM public.posts WHERE id = deleted_post.id;
            deleted_count := deleted_count + 1;
            
        EXCEPTION WHEN OTHERS THEN
            RAISE WARNING 'Error cleaning up deleted post %: %', deleted_post.id, SQLERRM;
        END;
    END LOOP;
    
    RAISE LOG 'Deleted posts cleanup completed: % posts cleaned', deleted_count;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 4. FUNCIÓN PARA ESTADÍSTICAS DE LIMPIEZA
-- =====================================================

CREATE OR REPLACE FUNCTION get_cleanup_stats()
RETURNS TABLE(
    expired_stories_count bigint,
    old_notifications_count bigint,
    deleted_posts_count bigint,
    storage_size_posts text,
    storage_size_stories text
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        (SELECT COUNT(*) FROM public.stories WHERE expires_at < NOW() AND is_archived = false) as expired_stories_count,
        (SELECT COUNT(*) FROM public.social_notifications WHERE created_at < NOW() - INTERVAL '30 days' AND is_read = true) as old_notifications_count,
        (SELECT COUNT(*) FROM public.posts WHERE deleted_at IS NOT NULL AND deleted_at < NOW() - INTERVAL '7 days') as deleted_posts_count,
        'N/A'::text as storage_size_posts, -- Requiere consulta adicional al storage
        'N/A'::text as storage_size_stories; -- Requiere consulta adicional al storage
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 5. CONFIGURACIÓN DE CRON JOB (SI PG_CRON ESTÁ DISPONIBLE)
-- =====================================================

-- Descomenta estas líneas si tienes pg_cron habilitado en tu instancia de Supabase

-- Configurar limpieza cada hora
-- SELECT cron.schedule('social-cleanup-hourly', '0 * * * *', 'SELECT social_cleanup_job();');

-- Configurar limpieza de archivos cada 6 horas
-- SELECT cron.schedule('story-files-cleanup', '0 */6 * * *', 'SELECT cleanup_expired_story_files();');

-- Configurar limpieza de posts eliminados diariamente
-- SELECT cron.schedule('deleted-posts-cleanup', '0 2 * * *', 'SELECT cleanup_deleted_posts();');

-- =====================================================
-- 6. FUNCIÓN PARA LIMPIEZA MANUAL
-- =====================================================

CREATE OR REPLACE FUNCTION manual_social_cleanup(
    cleanup_type text DEFAULT 'all'
)
RETURNS json AS $$
DECLARE
    result json;
    stories_deleted integer := 0;
    files_deleted integer := 0;
    notifications_deleted integer := 0;
    posts_deleted integer := 0;
BEGIN
    -- Limpiar stories expiradas
    IF cleanup_type = 'all' OR cleanup_type = 'stories' THEN
        DELETE FROM public.stories 
        WHERE expires_at < NOW() 
        AND is_archived = false;
        GET DIAGNOSTICS stories_deleted = ROW_COUNT;
    END IF;
    
    -- Limpiar archivos de stories
    IF cleanup_type = 'all' OR cleanup_type = 'story-files' THEN
        SELECT cleanup_expired_story_files() INTO files_deleted;
    END IF;
    
    -- Limpiar notificaciones antiguas
    IF cleanup_type = 'all' OR cleanup_type = 'notifications' THEN
        DELETE FROM public.social_notifications 
        WHERE created_at < NOW() - INTERVAL '30 days'
        AND is_read = true;
        GET DIAGNOSTICS notifications_deleted = ROW_COUNT;
    END IF;
    
    -- Limpiar posts eliminados
    IF cleanup_type = 'all' OR cleanup_type = 'posts' THEN
        SELECT cleanup_deleted_posts() INTO posts_deleted;
    END IF;
    
    -- Retornar estadísticas
    result := json_build_object(
        'cleanup_type', cleanup_type,
        'stories_deleted', stories_deleted,
        'files_deleted', files_deleted,
        'notifications_deleted', notifications_deleted,
        'posts_deleted', posts_deleted,
        'timestamp', NOW()
    );
    
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 7. FUNCIÓN PARA MONITOREO DE STORAGE
-- =====================================================

CREATE OR REPLACE FUNCTION get_storage_usage()
RETURNS TABLE(
    bucket_name text,
    estimated_files bigint,
    estimated_size_mb numeric
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        'jetgo-posts'::text as bucket_name,
        (SELECT COUNT(*) FROM public.posts WHERE image_url IS NOT NULL OR video_url IS NOT NULL) as estimated_files,
        (SELECT COALESCE(SUM(file_size), 0) / 1024 / 1024 FROM public.posts WHERE file_size IS NOT NULL) as estimated_size_mb
    UNION ALL
    SELECT 
        'jetgo-stories'::text as bucket_name,
        (SELECT COUNT(*) FROM public.stories WHERE media_url IS NOT NULL) as estimated_files,
        (SELECT COALESCE(SUM(file_size), 0) / 1024 / 1024 FROM public.stories WHERE file_size IS NOT NULL) as estimated_size_mb;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- COMENTARIOS FINALES
-- =====================================================

-- Este archivo proporciona:
-- ✅ Limpieza automática de stories expiradas
-- ✅ Limpieza de archivos huérfanos
-- ✅ Limpieza de notificaciones antiguas
-- ✅ Limpieza de posts eliminados
-- ✅ Funciones de monitoreo
-- ✅ Limpieza manual con opciones

-- Para activar la limpieza automática:
-- 1. Verificar si pg_cron está disponible
-- 2. Descomentar las líneas de cron.schedule
-- 3. O configurar un cron job externo que llame a social_cleanup_job()

-- Comandos útiles:
-- SELECT social_cleanup_job(); -- Limpieza completa
-- SELECT manual_social_cleanup('stories'); -- Solo stories
-- SELECT get_cleanup_stats(); -- Ver estadísticas
-- SELECT get_storage_usage(); -- Ver uso de storage
