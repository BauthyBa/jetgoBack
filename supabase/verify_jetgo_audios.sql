-- Script de verificación para el bucket jetgo-audios
-- Ejecutar en Supabase SQL Editor

-- ============================================
-- 1. VERIFICAR QUE EL BUCKET EXISTE
-- ============================================

SELECT 'BUCKET EXISTS:' as check_type,
       CASE 
         WHEN EXISTS (SELECT 1 FROM storage.buckets WHERE id = 'jetgo-audios') 
         THEN '✅ Bucket jetgo-audios existe'
         ELSE '❌ Bucket jetgo-audios NO existe'
       END as status;

-- ============================================
-- 2. VERIFICAR CONFIGURACIÓN DEL BUCKET
-- ============================================

SELECT 'BUCKET CONFIG:' as check_type,
       id, name, public, file_size_limit, allowed_mime_types, created_at
FROM storage.buckets 
WHERE id = 'jetgo-audios';

-- ============================================
-- 3. VERIFICAR POLÍTICAS RLS
-- ============================================

SELECT 'STORAGE POLICIES:' as check_type,
       policyname, permissive, roles, cmd, qual
FROM pg_policies 
WHERE tablename = 'objects' 
AND policyname LIKE '%jetgo-audios%'
ORDER BY policyname;

-- ============================================
-- 4. VERIFICAR ARCHIVOS EN EL BUCKET
-- ============================================

SELECT 'FILES IN BUCKET:' as check_type,
       name, bucket_id, owner, created_at, updated_at, last_accessed_at, metadata
FROM storage.objects 
WHERE bucket_id = 'jetgo-audios'
ORDER BY created_at DESC
LIMIT 10;

-- ============================================
-- 5. VERIFICAR FUNCIONES
-- ============================================

SELECT 'FUNCTIONS:' as check_type,
       routine_name, routine_type
FROM information_schema.routines 
WHERE routine_name IN (
  'generate_jetgo_audio_filename',
  'get_jetgo_audio_public_url'
)
ORDER BY routine_name;

-- ============================================
-- 6. VERIFICAR PERMISOS DE ESCRITURA
-- ============================================

-- Verificar que el bucket es público
SELECT 'PUBLIC ACCESS:' as check_type,
       CASE 
         WHEN EXISTS (SELECT 1 FROM storage.buckets WHERE id = 'jetgo-audios' AND public = true)
         THEN '✅ Bucket es público'
         ELSE '❌ Bucket no es público'
       END as status;

-- Verificar tipos MIME permitidos
SELECT 'ALLOWED MIME TYPES:' as check_type,
       unnest(allowed_mime_types) as mime_type
FROM storage.buckets 
WHERE id = 'jetgo-audios';

-- Verificar límite de tamaño
SELECT 'FILE SIZE LIMIT:' as check_type,
       file_size_limit,
       CASE 
         WHEN file_size_limit >= 10485760 THEN '✅ Límite suficiente (>= 10MB)'
         ELSE '❌ Límite insuficiente (< 10MB)'
       END as status
FROM storage.buckets 
WHERE id = 'jetgo-audios';

-- ============================================
-- 7. VERIFICAR CONFIGURACIÓN DE SUPABASE CLIENT
-- ============================================

-- Verificar que el cliente de Supabase puede acceder al bucket
SELECT 'SUPABASE CLIENT ACCESS:' as check_type,
       CASE 
         WHEN EXISTS (SELECT 1 FROM storage.buckets WHERE id = 'jetgo-audios' AND public = true)
         THEN '✅ Bucket es público y accesible'
         ELSE '❌ Bucket no es público o no accesible'
       END as status;

-- ============================================
-- 8. VERIFICAR BUCKETS ANTIGUOS
-- ============================================

-- Verificar si existen buckets antiguos problemáticos
SELECT 'OLD BUCKETS:' as check_type,
       id, name, public, created_at
FROM storage.buckets 
WHERE id IN ('chat-audios', 'jetgo-audios')
ORDER BY created_at;

-- ============================================
-- 9. RESUMEN DE VERIFICACIÓN
-- ============================================

SELECT 'VERIFICATION COMPLETE:' as check_type,
       'Revisar los resultados arriba para identificar problemas' as status;

-- ============================================
-- 10. INSTRUCCIONES DE USO
-- ============================================

SELECT 'NEXT STEPS:' as check_type,
       '1. Ejecutar create_jetgo_audios_bucket.sql si el bucket no existe
        2. Actualizar el backend para usar jetgo-audios
        3. Probar subida de audio con /api/chat/test-audio/
        4. Verificar que los archivos aparecen en Supabase Storage' as instructions;
