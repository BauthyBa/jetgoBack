#!/usr/bin/env python3
"""
Script para verificar y crear el bucket de avatars en Supabase
"""
import os
import sys
from supabase import create_client, Client

def check_and_create_bucket():
    # Configuración de Supabase
    url = os.environ.get('SUPABASE_URL', 'https://pamidjksvzshakzkrtdy.supabase.co')
    key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
    
    if not key:
        print("❌ SUPABASE_SERVICE_ROLE_KEY no encontrada en variables de entorno")
        return False
    
    try:
        # Crear cliente de Supabase
        supabase: Client = create_client(url, key)
        
        # Verificar si el bucket existe
        print("🔍 Verificando bucket 'avatars'...")
        buckets = supabase.storage.list_buckets()
        
        bucket_exists = False
        for bucket in buckets:
            if bucket.name == 'avatars':
                bucket_exists = True
                print(f"✅ Bucket 'avatars' encontrado: {bucket}")
                break
        
        if not bucket_exists:
            print("📦 Creando bucket 'avatars'...")
            try:
                result = supabase.storage.create_bucket(
                    'avatars',
                    options={
                        'public': True,
                        'file_size_limit': 5242880,  # 5MB
                        'allowed_mime_types': ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
                    }
                )
                print(f"✅ Bucket 'avatars' creado exitosamente: {result}")
            except Exception as e:
                print(f"❌ Error creando bucket: {e}")
                return False
        
        # Verificar políticas
        print("🔒 Verificando políticas de seguridad...")
        try:
            # Intentar subir un archivo de prueba para verificar permisos
            test_content = b"test"
            test_path = "test-file.txt"
            
            # Subir archivo de prueba
            result = supabase.storage.from_('avatars').upload(test_path, test_content)
            print(f"✅ Políticas de subida funcionando: {result}")
            
            # Eliminar archivo de prueba
            supabase.storage.from_('avatars').remove([test_path])
            print("✅ Archivo de prueba eliminado")
            
        except Exception as e:
            print(f"⚠️  Advertencia con políticas: {e}")
            print("💡 Puede que necesites configurar las políticas manualmente")
        
        print("✅ Verificación completada")
        return True
        
    except Exception as e:
        print(f"❌ Error conectando a Supabase: {e}")
        return False

if __name__ == "__main__":
    success = check_and_create_bucket()
    sys.exit(0 if success else 1)
