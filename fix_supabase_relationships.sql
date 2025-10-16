-- Script para solucionar las relaciones de Supabase
-- Ejecutar este script en el SQL Editor de Supabase

-- 1. Primero, vamos a verificar las tablas existentes
SELECT table_name, column_name, data_type 
FROM information_schema.columns 
WHERE table_schema = 'public' 
AND table_name IN ('posts', 'stories', 'User')
ORDER BY table_name, ordinal_position;

-- 2. Verificar las foreign keys existentes
SELECT 
    tc.table_name, 
    kcu.column_name, 
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name,
    tc.constraint_name
FROM 
    information_schema.table_constraints AS tc 
    JOIN information_schema.key_column_usage AS kcu
      ON tc.constraint_name = kcu.constraint_name
      AND tc.table_schema = kcu.table_schema
    JOIN information_schema.constraint_column_usage AS ccu
      ON ccu.constraint_name = tc.constraint_name
      AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY' 
AND tc.table_name IN ('posts', 'stories')
AND tc.table_schema = 'public';

-- 3. Si las foreign keys apuntan a auth.users, necesitamos cambiarlas
-- Primero, eliminamos las foreign keys existentes
ALTER TABLE public.posts DROP CONSTRAINT IF EXISTS posts_user_fk;
ALTER TABLE public.stories DROP CONSTRAINT IF EXISTS stories_user_fk;

-- 4. Agregamos las foreign keys correctas que apunten a public.User
ALTER TABLE public.posts 
ADD CONSTRAINT posts_user_fk 
FOREIGN KEY (user_id) REFERENCES public."User"(userid);

ALTER TABLE public.stories 
ADD CONSTRAINT stories_user_fk 
FOREIGN KEY (user_id) REFERENCES public."User"(userid);

-- 5. Verificar que las relaciones se crearon correctamente
SELECT 
    tc.table_name, 
    kcu.column_name, 
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name,
    tc.constraint_name
FROM 
    information_schema.table_constraints AS tc 
    JOIN information_schema.key_column_usage AS kcu
      ON tc.constraint_name = kcu.constraint_name
      AND tc.table_schema = kcu.table_schema
    JOIN information_schema.constraint_column_usage AS ccu
      ON ccu.constraint_name = tc.constraint_name
      AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY' 
AND tc.table_name IN ('posts', 'stories')
AND tc.table_schema = 'public';

-- 6. Opcional: Si quieres sincronizar datos entre auth.users y public.User
-- Esto es útil si tienes usuarios en auth.users que no están en public.User
INSERT INTO public."User" (userid, nombre, apellido, mail, created_at)
SELECT 
    au.id,
    COALESCE(au.raw_user_meta_data->>'full_name', 'Usuario') as nombre,
    '' as apellido,
    au.email,
    au.created_at
FROM auth.users au
WHERE au.id NOT IN (SELECT userid FROM public."User")
ON CONFLICT (userid) DO NOTHING;

-- 7. Verificar que todo está funcionando
SELECT 'Posts count:' as info, COUNT(*) as count FROM public.posts
UNION ALL
SELECT 'Stories count:' as info, COUNT(*) as count FROM public.stories
UNION ALL
SELECT 'Users count:' as info, COUNT(*) as count FROM public."User";
