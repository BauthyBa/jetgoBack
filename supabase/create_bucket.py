#!/usr/bin/env python3
"""
Script para crear el bucket de avatars usando la API REST de Supabase
"""
import requests
import json
import os

def create_avatars_bucket():
    # Configuración de Supabase
    url = "https://pamidjksvzshakzkrtdy.supabase.co"
    # Necesitas obtener el SERVICE_ROLE_KEY de tu proyecto Supabase
    service_key = "YOUR_SERVICE_ROLE_KEY_HERE"  # Reemplaza con tu service role key
    
    if service_key == "YOUR_SERVICE_ROLE_KEY_HERE":
        print("❌ Necesitas configurar SUPABASE_SERVICE_ROLE_KEY")
        print("💡 Ve a tu proyecto Supabase > Settings > API > service_role key")
        return False
    
    try:
        # Crear bucket usando la API REST
        headers = {
            'Authorization': f'Bearer {service_key}',
            'apikey': service_key,
            'Content-Type': 'application/json'
        }
        
        bucket_data = {
            'id': 'avatars',
            'name': 'avatars',
            'public': True,
            'file_size_limit': 5242880,  # 5MB
            'allowed_mime_types': ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
        }
        
        print("📦 Creando bucket 'avatars'...")
        response = requests.post(
            f"{url}/storage/v1/bucket",
            headers=headers,
            json=bucket_data,
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            print("✅ Bucket 'avatars' creado exitosamente")
            print(f"📋 Respuesta: {response.json()}")
            return True
        else:
            print(f"❌ Error creando bucket: {response.status_code}")
            print(f"📋 Respuesta: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Creando bucket de avatars...")
    print("⚠️  IMPORTANTE: Necesitas configurar SUPABASE_SERVICE_ROLE_KEY")
    print("💡 Ve a tu proyecto Supabase > Settings > API > service_role key")
    success = create_avatars_bucket()
    if not success:
        print("\n📝 INSTRUCCIONES MANUALES:")
        print("1. Ve a tu proyecto Supabase Dashboard")
        print("2. Navega a Storage")
        print("3. Haz clic en 'New bucket'")
        print("4. Configura:")
        print("   - Name: avatars")
        print("   - Public bucket: ✅")
        print("   - File size limit: 5 MB")
        print("   - Allowed MIME types: image/jpeg,image/png,image/gif,image/webp")
        print("5. Ejecuta el script SQL: supabase/avatars_bucket_setup.sql")
