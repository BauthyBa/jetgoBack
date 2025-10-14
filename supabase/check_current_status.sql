-- Script para verificar el estado actual de la base de datos
-- NO crea ni modifica nada, solo verifica
-- Ejecutar en Supabase SQL Editor

-- ============================================
-- 1. VERIFICAR BUCKETS EXISTENTES
-- ============================================

SELECT 'EXISTING BUCKETS:' as check_type,
       id, name, public, file_size_limit, created_at
FROM storage.buckets 
ORDER BY created_at DESC;

-- ============================================
-- 2. VERIFICAR BUCKET JETGO-AUDIOS
-- ============================================

SELECT 'JETGO-AUDIOS BUCKET:' as check_type,
       CASE 
         WHEN EXISTS (SELECT 1 FROM storage.buckets WHERE id = 'jetgo-audios') 
         THEN '✅ Bucket jetgo-audios existe'
         ELSE '❌ Bucket jetgo-audios NO existe'
       END as status;

-- ============================================
-- 3. VERIFICAR CONFIGURACIÓN DEL BUCKET
-- ============================================

SELECT 'BUCKET CONFIG:' as check_type,
       id, name, public, file_size_limit, allowed_mime_types, created_at
FROM storage.buckets 
WHERE id = 'jetgo-audios';

-- ============================================
-- 4. VERIFICAR POLÍTICAS RLS
-- ============================================

SELECT 'STORAGE POLICIES:' as check_type,
       policyname, permissive, roles, cmd
FROM pg_policies 
WHERE tablename = 'objects' 
AND policyname LIKE '%jetgo-audios%'
ORDER BY policyname;

-- ============================================
-- 5. VERIFICAR ARCHIVOS EN EL BUCKET
-- ============================================

SELECT 'FILES IN JETGO-AUDIOS:' as check_type,
       name, bucket_id, owner, created_at, updated_at, metadata
FROM storage.objects 
WHERE bucket_id = 'jetgo-audios'
ORDER BY created_at DESC
LIMIT 10;

-- ============================================
-- 6. VERIFICAR FUNCIONES
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
-- 7. VERIFICAR TABLAS EXISTENTES
-- ============================================

SELECT 'EXISTING TABLES:' as check_type,
       table_name, table_type
FROM information_schema.tables 
WHERE table_schema = 'public'
AND table_name IN ('applications', 'chat_messages', 'notifications', 'trips')
ORDER BY table_name;

-- ============================================
-- 8. VERIFICAR COLUMNAS DE AUDIO EN CHAT_MESSAGES
-- ============================================

SELECT 'AUDIO COLUMNS IN CHAT_MESSAGES:' as check_type,
       column_name, data_type, is_nullable
FROM information_schema.columns 
WHERE table_name = 'chat_messages' 
AND column_name IN ('audio_duration', 'audio_waveform')
ORDER BY column_name;

-- ============================================
-- 9. VERIFICAR TRANSPORT_TYPE EN TRIPS
-- ============================================

SELECT 'TRANSPORT TYPE IN TRIPS:' as check_type,
       column_name, data_type, is_nullable, column_default
FROM information_schema.columns 
WHERE table_name = 'trips' 
AND column_name = 'transport_type';

-- ============================================
-- 10. RESUMEN DEL ESTADO
-- ============================================

SELECT 'CURRENT STATUS:' as check_type,
       'Revisar los resultados arriba para ver el estado actual de la configuración' as message;
