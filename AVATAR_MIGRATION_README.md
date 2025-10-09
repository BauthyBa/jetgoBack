# Migración de Avatar URL

## Problema
Las fotos de perfil no aparecen en los perfiles públicos porque la URL del avatar se almacena en `user_metadata` de Supabase Auth, pero no está disponible en la tabla `User` para consultas públicas.

## Solución
Agregar la columna `avatar_url` a la tabla `User` y sincronizar los datos existentes.

## Pasos para ejecutar la migración

### 1. Ejecutar el script SQL en Supabase Dashboard

1. Ve a tu proyecto de Supabase
2. Navega a **SQL Editor**
3. Copia y pega el contenido de `supabase/add_avatar_url_column.sql`
4. Ejecuta el script

### 2. Verificar la migración

```sql
-- Verificar que la columna existe
SELECT userid, avatar_url FROM public."User" LIMIT 5;

-- Verificar que los datos se sincronizaron
SELECT COUNT(*) as total_users, 
       COUNT(avatar_url) as users_with_avatar 
FROM public."User";
```

### 3. Probar la funcionalidad

1. Ve a un perfil público (ej: `/u/800fa7b8-837e-4110-ab1d-695a2abc1cfe`)
2. Verifica que la foto de perfil aparece correctamente
3. Si no aparece, verifica que el usuario tenga `avatar_url` en la tabla `User`

## Archivos modificados

### Backend
- `jetgoBack/supabase/add_avatar_url_column.sql` - Script de migración
- `jetgoBack/run_avatar_migration.py` - Script de Python para automatizar

### Frontend
- `jetgoFront/src/pages/PublicProfile.jsx` - Usa `avatar_url` de tabla `User`
- `jetgoMobile/src/pages/PublicProfile.jsx` - Usa `avatar_url` de tabla `User`
- `jetgoFront/src/components/ProfileCard.jsx` - Sincroniza `avatar_url` en tabla `User`

## Funcionalidades implementadas

### ✅ Sincronización automática
- Trigger que mantiene sincronizado `avatar_url` entre `auth.users` y `public.User`
- Cuando se actualiza `user_metadata.avatar_url`, se actualiza automáticamente en la tabla `User`

### ✅ Consulta directa
- Los perfiles públicos ahora consultan `avatar_url` directamente de la tabla `User`
- No requiere autenticación ni endpoints adicionales

### ✅ Actualización bidireccional
- Cuando un usuario actualiza su avatar, se actualiza tanto en `user_metadata` como en la tabla `User`
- Mantiene consistencia entre ambos sistemas

## Verificación post-migración

1. **Verificar columna**: `SELECT avatar_url FROM public."User" LIMIT 1;`
2. **Verificar sincronización**: Actualizar avatar y verificar que se sincroniza
3. **Verificar perfiles públicos**: Visitar perfiles de otros usuarios
4. **Verificar trigger**: El trigger debe mantener sincronización automática

## Rollback (si es necesario)

```sql
-- Eliminar trigger
DROP TRIGGER IF EXISTS sync_avatar_trigger ON auth.users;

-- Eliminar función
DROP FUNCTION IF EXISTS sync_avatar_on_user_update();

-- Eliminar columna (CUIDADO: esto eliminará los datos)
ALTER TABLE public."User" DROP COLUMN IF EXISTS avatar_url;
```
