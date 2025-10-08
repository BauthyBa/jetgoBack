# Solución para el problema de avatars

## Problema identificado
- **Error RLS**: "new row violates row-level security policy"
- **Archivo no se guarda**: Las imágenes no se suben al bucket

## Causa del problema
Las políticas de RLS están configuradas para esperar que los archivos estén en una estructura de carpetas: `userId/filename`, pero el código estaba subiendo archivos directamente al bucket sin crear esa estructura.

## Solución implementada

### 1. Cambios en el código (ya aplicados)
- ✅ Modificado `AvatarUpload.jsx` en `jetgoFront` y `jetgoMobile`
- ✅ Cambiado el nombre del archivo de `${userId}-${Date.now()}.${fileExt}` a `${userId}/${userId}-${Date.now()}.${fileExt}`
- ✅ Actualizada la función de eliminación para manejar la nueva estructura de carpetas

### 2. Pasos para completar la solución

#### Paso 1: Ejecutar el script de corrección en Supabase
1. Ve a tu proyecto de Supabase
2. Abre el **SQL Editor**
3. Ejecuta el contenido del archivo `fix_avatars_bucket.sql`
4. Verifica que no haya errores

#### Paso 2: Verificar la configuración
1. Ve a **Storage** en el dashboard de Supabase
2. Verifica que el bucket `avatars` existe
3. Verifica que las políticas están configuradas correctamente

#### Paso 3: Probar la funcionalidad
1. Configura las variables de entorno:
   ```bash
   export SUPABASE_URL="https://pamidjksvzshakzkrtdy.supabase.co"
   export SUPABASE_ANON_KEY="tu_anon_key_aqui"
   ```
2. Ejecuta el script de prueba:
   ```bash
   python3 test_avatar_upload.py
   ```

## Estructura de archivos esperada
```
avatars/
├── user-id-1/
│   ├── user-id-1-1234567890.jpg
│   └── user-id-1-1234567891.png
├── user-id-2/
│   └── user-id-2-1234567892.jpg
└── ...
```

## Políticas RLS configuradas
- ✅ Usuarios pueden subir archivos solo en su propia carpeta
- ✅ Usuarios pueden actualizar sus propios archivos
- ✅ Usuarios pueden eliminar sus propios archivos
- ✅ Todos los avatars son públicamente legibles

## Verificación final
Después de aplicar estos cambios:
1. Intenta subir una imagen en el perfil
2. Verifica que no aparezca el error RLS
3. Verifica que la imagen se guarde en el bucket
4. Verifica que la imagen se muestre correctamente en el perfil
