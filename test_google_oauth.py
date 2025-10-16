#!/usr/bin/env python3
"""
Script de prueba para el endpoint de Google OAuth
Uso: python test_google_oauth.py <access_token>
"""
import sys
import requests
import json

def test_google_auth(access_token):
    """Prueba el endpoint de autenticación con Google"""
    url = 'http://127.0.0.1:8000/api/users/auth/google/'
    
    payload = {
        'access_token': access_token
    }
    
    print(f"🔍 Probando endpoint: {url}")
    print(f"📤 Enviando token: {access_token[:50]}...")
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        
        print(f"\n📥 Status Code: {response.status_code}")
        print(f"📥 Response Headers: {dict(response.headers)}")
        
        try:
            data = response.json()
            print(f"\n📥 Response Body:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            if data.get('ok'):
                print("\n✅ Autenticación exitosa!")
                user = data.get('user', {})
                print(f"   - Usuario ID: {user.get('id')}")
                print(f"   - Email: {user.get('email')}")
                print(f"   - Nombre: {user.get('first_name')} {user.get('last_name')}")
                print(f"   - Avatar: {user.get('avatar_url')}")
            else:
                print(f"\n❌ Error: {data.get('error')}")
        except Exception as e:
            print(f"\n❌ Error al parsear JSON: {e}")
            print(f"Response text: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Error de conexión: {e}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("❌ Uso: python test_google_oauth.py <access_token>")
        print("\nPara obtener un access_token:")
        print("1. Inicia sesión con Google en el frontend")
        print("2. Abre la consola del navegador")
        print("3. Ejecuta: supabase.auth.getSession()")
        print("4. Copia el access_token de la respuesta")
        sys.exit(1)
    
    access_token = sys.argv[1]
    test_google_auth(access_token)
