#!/usr/bin/env python3
"""
Script para probar la funcionalidad de upload de avatars
"""
import os
import sys
from supabase import create_client, Client
import io
import base64

def test_avatar_upload():
    # Configuración de Supabase
    url = os.environ.get('SUPABASE_URL', 'https://pamidjksvzshakzkrtdy.supabase.co')
    key = os.environ.get('SUPABASE_ANON_KEY')
    
    if not key:
        print("❌ SUPABASE_ANON_KEY no encontrada en variables de entorno")
        return False
    
    try:
        # Crear cliente de Supabase
        supabase: Client = create_client(url, key)
        
        # Verificar que el bucket existe
        print("🔍 Verificando bucket 'avatars'...")
        buckets = supabase.storage.list_buckets()
        
        bucket_exists = False
        for bucket in buckets:
            if bucket.name == 'avatars':
                bucket_exists = True
                print(f"✅ Bucket 'avatars' encontrado: {bucket}")
                break
        
        if not bucket_exists:
            print("❌ Bucket 'avatars' no existe. Ejecuta el script fix_avatars_bucket.sql primero.")
            return False
        
        # Crear un archivo de prueba (imagen pequeña en base64)
        test_image_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        
        # Simular un user_id de prueba
        test_user_id = "test-user-123"
        test_filename = f"{test_user_id}/{test_user_id}-test.png"
        
        print(f"📤 Intentando subir archivo de prueba: {test_filename}")
        
        # Intentar subir el archivo
        try:
            result = supabase.storage.from_('avatars').upload(
                test_filename,
                test_image_data,
                file_options={
                    'content-type': 'image/png',
                    'cache-control': '3600'
                }
            )
            
            if result.get('error'):
                print(f"❌ Error en upload: {result['error']}")
                return False
            else:
                print(f"✅ Upload exitoso: {result}")
                
                # Intentar obtener la URL pública
                try:
                    public_url = supabase.storage.from_('avatars').get_public_url(test_filename)
                    print(f"🔗 URL pública: {public_url}")
                except Exception as e:
                    print(f"⚠️ No se pudo obtener URL pública: {e}")
                
                # Limpiar archivo de prueba
                try:
                    supabase.storage.from_('avatars').remove([test_filename])
                    print("🧹 Archivo de prueba eliminado")
                except Exception as e:
                    print(f"⚠️ No se pudo eliminar archivo de prueba: {e}")
                
                return True
                
        except Exception as e:
            print(f"❌ Error durante upload: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Error general: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Probando funcionalidad de avatars...")
    success = test_avatar_upload()
    if success:
        print("✅ Prueba completada exitosamente")
    else:
        print("❌ Prueba falló")
        sys.exit(1)
