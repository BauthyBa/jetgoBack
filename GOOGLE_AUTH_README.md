# Autenticación con Google OAuth

## Endpoint Implementado

**URL:** `POST /api/auth/google/`

Este endpoint maneja la autenticación con Google OAuth a través de Supabase.

## Cómo Funciona

### Opción 1: Enviar tokens directamente (Recomendado)

Si el frontend ya obtuvo los tokens de Supabase usando `signInWithOAuth`:

```javascript
// En el frontend (React/Vue/etc)
const { data, error } = await supabase.auth.signInWithOAuth({
  provider: 'google',
  options: {
    redirectTo: `${window.location.origin}/auth/callback`
  }
})

// Después del callback, obtener la sesión
const { data: { session } } = await supabase.auth.getSession()

// Enviar al backend
const response = await fetch('http://tu-backend/api/auth/google/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    access_token: session.access_token,
    refresh_token: session.refresh_token
  })
})

const result = await response.json()
// result contiene: { access, refresh, user_id }
```

### Opción 2: Enviar código de autorización

Si tienes un código de autorización de Google:

```javascript
const response = await fetch('http://tu-backend/api/auth/google/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    code: 'codigo_de_autorizacion_de_google'
  })
})
```

## Request Body

El endpoint acepta uno de estos formatos:

### Formato 1: Tokens
```json
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc..."
}
```

### Formato 2: Código
```json
{
  "code": "4/0AY0e-g7..."
}
```

## Response

### Éxito (200 OK)
```json
{
  "access": "eyJhbGc...",
  "refresh": "eyJhbGc...",
  "user_id": "uuid-del-usuario"
}
```

### Error (400 Bad Request)
```json
{
  "error": "Descripción del error"
}
```

## Qué Hace el Endpoint

1. **Valida los tokens o código** con Supabase
2. **Obtiene los datos del usuario** de Google (nombre, email, avatar)
3. **Crea o actualiza el usuario** en la tabla `User` de PostgreSQL
4. **Retorna los tokens** para que el frontend los use en futuras peticiones

## Datos del Usuario

El endpoint extrae automáticamente:
- **Email** del usuario de Google
- **Nombre y apellido** (de `given_name` y `family_name`)
- **Avatar** (foto de perfil de Google)
- **Email confirmado** (se marca como `true` automáticamente)

## Configuración Necesaria en Supabase

Para que funcione, debes configurar Google OAuth en tu proyecto de Supabase:

1. Ve a **Authentication > Providers** en el dashboard de Supabase
2. Habilita **Google**
3. Configura las credenciales de OAuth de Google:
   - Client ID
   - Client Secret
4. Agrega las URLs de redirección autorizadas

## Ejemplo de Flujo Completo

```javascript
// 1. Usuario hace clic en "Iniciar sesión con Google"
const handleGoogleLogin = async () => {
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: 'google',
    options: {
      redirectTo: `${window.location.origin}/auth/callback`
    }
  })
}

// 2. En la página de callback (/auth/callback)
useEffect(() => {
  const handleCallback = async () => {
    // Obtener la sesión después del redirect
    const { data: { session }, error } = await supabase.auth.getSession()
    
    if (session) {
      // Enviar al backend para sincronizar con la base de datos
      const response = await fetch('http://tu-backend/api/auth/google/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          access_token: session.access_token,
          refresh_token: session.refresh_token
        })
      })
      
      const result = await response.json()
      
      // Guardar tokens en localStorage o estado global
      localStorage.setItem('access_token', result.access)
      localStorage.setItem('refresh_token', result.refresh)
      localStorage.setItem('user_id', result.user_id)
      
      // Redirigir al dashboard o página principal
      navigate('/dashboard')
    }
  }
  
  handleCallback()
}, [])
```

## Notas Importantes

- Los usuarios que inician sesión con Google **no necesitan confirmar su email** (ya está verificado por Google)
- El avatar de Google se guarda automáticamente en el campo `avatar_url`
- Si el usuario ya existe (mismo email), se actualiza su información
- Los tokens retornados son de Supabase, no de Google directamente
