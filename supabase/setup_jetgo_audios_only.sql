-- Script SOLO para configurar el bucket jetgo-audios
-- NO toca las tablas existentes
-- Ejecutar en Supabase SQL Editor

-- ============================================
-- 1. ELIMINAR BUCKETS PROBLEMÁTICOS EXISTENTES
-- ============================================

-- Eliminar archivos de buckets problemáticos
DELETE FROM storage.objects WHERE bucket_id IN ('chat-audios', 'jetgo-audios');

-- Eliminar buckets problemáticos
DELETE FROM storage.buckets WHERE id IN ('chat-audios', 'jetgo-audios');

-- ============================================
-- 2. CREAR BUCKET JETGO-AUDIOS
-- ============================================

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'jetgo-audios',
    'jetgo-audios', 
    true,
    10485760, -- 10MB límite
    ARRAY['audio/webm', 'audio/mp3', 'audio/wav', 'audio/ogg', 'audio/m4a', 'audio/mpeg', 'audio/x-m4a']
);

-- ============================================
-- 3. CONFIGURAR POLÍTICAS RLS
-- ============================================

-- Eliminar políticas existentes si existen
DROP POLICY IF EXISTS "Public read access for jetgo audios" ON storage.objects;
DROP POLICY IF EXISTS "Authenticated users can upload jetgo audios" ON storage.objects;
DROP POLICY IF EXISTS "Users can update their own jetgo audios" ON storage.objects;
DROP POLICY IF EXISTS "Users can delete their own jetgo audios" ON storage.objects;

-- Crear políticas nuevas
CREATE POLICY "Public read access for jetgo audios" ON storage.objects
FOR SELECT USING (bucket_id = 'jetgo-audios');

CREATE POLICY "Authenticated users can upload jetgo audios" ON storage.objects
FOR INSERT WITH CHECK (
    bucket_id = 'jetgo-audios' 
    AND auth.role() = 'authenticated'
);

CREATE POLICY "Users can update their own jetgo audios" ON storage.objects
FOR UPDATE USING (
    bucket_id = 'jetgo-audios' 
    AND auth.uid()::text = (storage.foldername(name))[1]
);

CREATE POLICY "Users can delete their own jetgo audios" ON storage.objects
FOR DELETE USING (
    bucket_id = 'jetgo-audios' 
    AND auth.uid()::text = (storage.foldername(name))[1]
);

-- ============================================
-- 4. CREAR FUNCIONES UTILITARIAS
-- ============================================

-- Función para generar nombre único de archivo de audio
CREATE OR REPLACE FUNCTION generate_jetgo_audio_filename(user_uuid uuid, room_uuid uuid)
RETURNS text AS $$
BEGIN
    RETURN 'audios/' || user_uuid::text || '/' || room_uuid::text || '/' || 
           extract(epoch from now())::bigint || '_' || 
           substring(md5(random()::text) from 1 for 8) || '.webm';
END;
$$ LANGUAGE plpgsql;

-- Función para obtener URL pública de audio
CREATE OR REPLACE FUNCTION get_jetgo_audio_public_url(file_path text)
RETURNS text AS $$
BEGIN
    RETURN 'https://[TU-PROYECTO-ID].supabase.co/storage/v1/object/public/jetgo-audios/' || file_path;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- 5. VERIFICAR CONFIGURACIÓN
-- ============================================

-- Verificar que el bucket se creó correctamente
SELECT 'BUCKET CREATED:' as status, 
       id, name, public, file_size_limit, allowed_mime_types, created_at
FROM storage.buckets 
WHERE id = 'jetgo-audios';

-- Verificar políticas
SELECT 'POLICIES CREATED:' as status,
       policyname, permissive, roles, cmd
FROM pg_policies 
WHERE tablename = 'objects' 
AND policyname LIKE '%jetgo-audios%'
ORDER BY policyname;

-- Verificar funciones
SELECT 'FUNCTIONS CREATED:' as status,
       routine_name, routine_type
FROM information_schema.routines 
WHERE routine_name IN ('generate_jetgo_audio_filename', 'get_jetgo_audio_public_url');

-- ============================================
-- 6. VERIFICAR PERMISOS
-- ============================================

-- Verificar que el bucket es público
SELECT 'PUBLIC ACCESS:' as status,
       CASE 
         WHEN EXISTS (SELECT 1 FROM storage.buckets WHERE id = 'jetgo-audios' AND public = true)
         THEN '✅ Bucket es público'
         ELSE '❌ Bucket no es público'
       END as result;

-- Verificar tipos MIME permitidos
SELECT 'ALLOWED MIME TYPES:' as status,
       unnest(allowed_mime_types) as mime_type
FROM storage.buckets 
WHERE id = 'jetgo-audios';

-- Verificar límite de tamaño
SELECT 'FILE SIZE LIMIT:' as status,
       file_size_limit,
       CASE 
         WHEN file_size_limit >= 10485760 THEN '✅ Límite suficiente (>= 10MB)'
         ELSE '❌ Límite insuficiente (< 10MB)'
       END as result
FROM storage.buckets 
WHERE id = 'jetgo-audios';

-- ============================================
-- 7. RESUMEN
-- ============================================

SELECT 'SETUP COMPLETE:' as status,
       'Bucket jetgo-audios configurado correctamente. Ahora puedes probar la subida de audios.' as message;
