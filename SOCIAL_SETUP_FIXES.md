# 🔧 Arreglos para Social Page - Supabase

## Errores corregidos:

### ✅ 1. **Frontend - Tablas incorrectas**
- ❌ `friendships` → ✅ `friend_requests` 
- ❌ `trip_participants` → ✅ `trip_members`
- ❌ `user.id` → ✅ `user.userid` (para queries de User table)

### ✅ 2. **Backend - Views.py ya configurado**
El backend de `social/views.py` ya está 100% configurado para Supabase:
- ✅ `PostListCreateView` - usa Supabase Storage bucket `jetgo-posts`
- ✅ `StoryListCreateView` - usa Supabase Storage bucket `jetgo-stories`
- ✅ `CommentListCreateView` - usa tabla `post_comments`
- ✅ `PostLikeView` - usa tabla `post_likes`

## 📋 Pasos para completar la configuración:

### 1. **Configurar bucket jetgo-stories en Supabase**

Ve a tu dashboard de Supabase y ejecuta el SQL:

```bash
# Archivo: jetgoBack/supabase/verify_stories_bucket.sql
```

O manualmente:
1. Ve a **Storage** en Supabase Dashboard
2. Crea un bucket llamado `jetgo-stories`
3. Marca como **Public**
4. Configura las políticas RLS (ver archivo SQL)

### 2. **Verificar bucket jetgo-posts**

Asegúrate de que el bucket `jetgo-posts` también exista:
1. Ve a **Storage** en Supabase Dashboard
2. Verifica que existe `jetgo-posts`
3. Debe ser **Public**
4. Con políticas RLS correctas

### 3. **Variables de entorno del backend**

Verifica que tu `.env` en `jetgoBack` tenga:

```env
SUPABASE_URL=https://pamidjksvzshakzkrtdy.supabase.co
SUPABASE_SERVICE_ROLE_KEY=tu_service_role_key_aqui
SUPABASE_ANON_KEY=tu_anon_key_aqui
```

## 🎯 Cambios realizados en el código:

### Frontend (`jetgoFront/src/pages/SocialPage.jsx`):

1. **getCurrentUser()**:
   - Ahora carga datos completos desde tabla `User`
   - Combina authUser con userData
   - Maneja errores si el usuario no existe en tabla User

2. **loadSuggestions()**:
   - Usa `friend_requests` en lugar de `friendships`
   - Usa `trip_members` en lugar de `trip_participants`
   - Usa `user.userid` para queries de Supabase
   - Manejo correcto de casos sin amigos/viajes

3. **Avatar del usuario**:
   - Muestra `user.avatar_url` en "Tu historia"
   - Muestra `user.avatar_url` en "Ver perfil"
   - Muestra nombre completo en lugar de email

## 🗄️ Estructura de tablas correcta:

```sql
-- Amigos
friend_requests (
  sender_id, 
  receiver_id, 
  status: 'pending' | 'accepted' | 'rejected'
)

-- Miembros de viajes
trip_members (
  trip_id,
  user_id,
  role,
  joined_at
)

-- Usuarios
User (
  userid (PK, uuid),
  nombre,
  apellido,
  avatar_url,
  bio,
  mail
)
```

## ✨ Funcionalidades implementadas:

- ✅ Feed de posts con likes y comentarios
- ✅ Stories con expiración 24h
- ✅ Sistema de comentarios funcional
- ✅ Compartir posts a chats
- ✅ Sugerencias de usuarios (excluye amigos)
- ✅ Sugerencias de viajes (excluye viajes del usuario)
- ✅ Avatar de perfil cargado desde Supabase
- ✅ Nombre completo del usuario

## 🐛 Si siguen apareciendo errores:

### Error 400 en User table:
- Verifica que el `userid` en tabla User sea tipo `UUID`
- Verifica que el usuario esté registrado en tabla User

### Error 404 en alguna tabla:
- Verifica que las tablas existan en Supabase
- Revisa los nombres exactos en el Schema

### Error de Storage:
- Verifica que los buckets existan
- Verifica que sean públicos
- Verifica las políticas RLS

## 🔍 Debug:

Para ver qué está pasando, abre la consola del navegador:
```javascript
// Deberías ver:
console.log('User data:', user)
// { id: 'uuid', userid: 'uuid', nombre: '...', apellido: '...', avatar_url: '...' }
```

## 📞 Siguientes pasos:

1. ✅ Ejecutar SQL para crear bucket jetgo-stories
2. ✅ Verificar variables de entorno
3. ✅ Probar subir una story
4. ✅ Probar crear un post
5. ✅ Verificar que aparezca el avatar
6. ✅ Verificar sugerencias de usuarios







