# Configuración de Avatars en Supabase

## Pasos para configurar el bucket de avatars

### 1. Crear el bucket en Supabase Dashboard

1. Ve a tu proyecto de Supabase
2. Navega a **Storage** en el menú lateral
3. Haz clic en **New bucket**
4. Configura el bucket con los siguientes valores:
   - **Name**: `avatars`
   - **Public bucket**: ✅ (marcado)
   - **File size limit**: `5 MB`
   - **Allowed MIME types**: `image/jpeg,image/png,image/gif,image/webp`

### 2. Ejecutar el script SQL

Ejecuta el archivo `avatars_bucket_setup.sql` en el SQL Editor de Supabase:

```sql
-- Crear bucket para avatars de usuarios
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'avatars',
  'avatars',
  true,
  5242880, -- 5MB limit
  ARRAY['image/jpeg', 'image/png', 'image/gif', 'image/webp']
);

-- Política para permitir que usuarios autenticados suban sus propios avatars
CREATE POLICY "Users can upload their own avatars" ON storage.objects
FOR INSERT WITH CHECK (
  bucket_id = 'avatars' 
  AND auth.uid()::text = (storage.foldername(name))[1]
);

-- Política para permitir que usuarios autenticados actualicen sus propios avatars
CREATE POLICY "Users can update their own avatars" ON storage.objects
FOR UPDATE USING (
  bucket_id = 'avatars' 
  AND auth.uid()::text = (storage.foldername(name))[1]
);

-- Política para permitir que usuarios autenticados eliminen sus propios avatars
CREATE POLICY "Users can delete their own avatars" ON storage.objects
FOR DELETE USING (
  bucket_id = 'avatars' 
  AND auth.uid()::text = (storage.foldername(name))[1]
);

-- Política para permitir lectura pública de avatars
CREATE POLICY "Avatars are publicly readable" ON storage.objects
FOR SELECT USING (bucket_id = 'avatars');

-- Función para generar nombres de archivo únicos
CREATE OR REPLACE FUNCTION generate_avatar_filename(user_id UUID, file_extension TEXT)
RETURNS TEXT AS $$
BEGIN
  RETURN user_id::text || '-' || extract(epoch from now())::bigint || '.' || file_extension;
END;
$$ LANGUAGE plpgsql;
```

### 3. Aplicar migración de Django

En el backend, ejecuta la migración para agregar el campo `avatar_url`:

```bash
cd /home/bautista/C/jetgoBack
source venv/bin/activate
python manage.py migrate users
```

### 4. Verificar configuración

1. **Bucket creado**: Verifica que el bucket `avatars` aparezca en Storage
2. **Políticas aplicadas**: Ve a **Authentication > Policies** y verifica que las políticas de storage estén activas
3. **Campo agregado**: Verifica que la tabla `User` tenga el campo `avatar_url`

## Funcionalidades implementadas

### Frontend (Mobile)
- ✅ Componente `AvatarUpload` con preview y validación
- ✅ Integración en `ProfileCard` con ícono de lápiz en hover
- ✅ Upload directo a Supabase Storage
- ✅ Manejo de errores y estados de carga

### Backend
- ✅ Campo `avatar_url` en modelo User
- ✅ Migración de base de datos
- ✅ Serializer actualizado para manejar avatar_url
- ✅ Vista UpsertProfileView actualizada

### Supabase
- ✅ Bucket `avatars` configurado
- ✅ Políticas de seguridad implementadas
- ✅ Límites de tamaño y tipo de archivo

## Uso

Los usuarios pueden:
1. Hacer hover sobre su avatar en el perfil
2. Ver el ícono de lápiz para editar
3. Seleccionar una imagen (JPEG, PNG, GIF, WebP)
4. Ver preview antes de subir
5. Eliminar su avatar actual
6. La imagen se guarda automáticamente en Supabase Storage
