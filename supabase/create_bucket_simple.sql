-- Script simple para crear el bucket jetgo-audios
-- Ejecutar en Supabase SQL Editor

-- 1. Eliminar bucket existente si existe
DELETE FROM storage.objects WHERE bucket_id = 'jetgo-audios';
DELETE FROM storage.buckets WHERE id = 'jetgo-audios';

-- 2. Crear bucket jetgo-audios
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'jetgo-audios',
    'jetgo-audios',
    true,
    10485760, -- 10MB
    ARRAY[
        'audio/webm',
        'audio/webm;codecs=opus',
        'audio/mp3',
        'audio/wav',
        'audio/ogg',
        'audio/m4a',
        'audio/mpeg',
        'audio/x-m4a'
    ]
);

-- 3. Crear políticas RLS
INSERT INTO storage.policies (id, bucket_id, name, definition, check_expression)
VALUES (
    'jetgo-audios-insert-policy',
    'jetgo-audios',
    'Allow authenticated users to upload audio files',
    'bucket_id = ''jetgo-audios''',
    'auth.role() = ''authenticated'''
);

INSERT INTO storage.policies (id, bucket_id, name, definition, check_expression)
VALUES (
    'jetgo-audios-select-policy',
    'jetgo-audios',
    'Allow authenticated users to view audio files',
    'bucket_id = ''jetgo-audios''',
    'auth.role() = ''authenticated'''
);

-- 4. Verificar que se creó correctamente
SELECT * FROM storage.buckets WHERE id = 'jetgo-audios';





