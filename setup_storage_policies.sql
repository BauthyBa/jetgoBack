-- Script para configurar políticas de Supabase Storage
-- Ejecutar en el SQL Editor de Supabase Dashboard

-- 1. Habilitar RLS en los buckets
ALTER TABLE storage.buckets ENABLE ROW LEVEL SECURITY;

-- 2. Política para jetgo-posts (lectura pública, escritura autenticada)
CREATE POLICY "jetgo-posts-public-read" ON storage.objects
FOR SELECT USING (bucket_id = 'jetgo-posts');

CREATE POLICY "jetgo-posts-authenticated-insert" ON storage.objects
FOR INSERT WITH CHECK (
  bucket_id = 'jetgo-posts' 
  AND auth.role() = 'authenticated'
);

CREATE POLICY "jetgo-posts-authenticated-update" ON storage.objects
FOR UPDATE USING (
  bucket_id = 'jetgo-posts' 
  AND auth.role() = 'authenticated'
);

CREATE POLICY "jetgo-posts-authenticated-delete" ON storage.objects
FOR DELETE USING (
  bucket_id = 'jetgo-posts' 
  AND auth.role() = 'authenticated'
);

-- 3. Política para jetgo-stories (lectura pública, escritura autenticada)
CREATE POLICY "jetgo-stories-public-read" ON storage.objects
FOR SELECT USING (bucket_id = 'jetgo-stories');

CREATE POLICY "jetgo-stories-authenticated-insert" ON storage.objects
FOR INSERT WITH CHECK (
  bucket_id = 'jetgo-stories' 
  AND auth.role() = 'authenticated'
);

CREATE POLICY "jetgo-stories-authenticated-update" ON storage.objects
FOR UPDATE USING (
  bucket_id = 'jetgo-stories' 
  AND auth.role() = 'authenticated'
);

CREATE POLICY "jetgo-stories-authenticated-delete" ON storage.objects
FOR DELETE USING (
  bucket_id = 'jetgo-stories' 
  AND auth.role() = 'authenticated'
);

-- 4. Política para jetgo-avatars (lectura pública, escritura autenticada)
CREATE POLICY "jetgo-avatars-public-read" ON storage.objects
FOR SELECT USING (bucket_id = 'jetgo-avatars');

CREATE POLICY "jetgo-avatars-authenticated-insert" ON storage.objects
FOR INSERT WITH CHECK (
  bucket_id = 'jetgo-avatars' 
  AND auth.role() = 'authenticated'
);

CREATE POLICY "jetgo-avatars-authenticated-update" ON storage.objects
FOR UPDATE USING (
  bucket_id = 'jetgo-avatars' 
  AND auth.role() = 'authenticated'
);

CREATE POLICY "jetgo-avatars-authenticated-delete" ON storage.objects
FOR DELETE USING (
  bucket_id = 'jetgo-avatars' 
  AND auth.role() = 'authenticated'
);

-- 5. Verificar que las políticas se crearon
SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual 
FROM pg_policies 
WHERE tablename = 'objects' 
AND schemaname = 'storage'
ORDER BY policyname;

-- 6. Mensaje de éxito
SELECT 'Políticas de Storage configuradas exitosamente' as resultado;
