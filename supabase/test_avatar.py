#!/usr/bin/env python3
"""
Script simple para probar la funcionalidad de avatars
"""
import os
import sys
sys.path.append('/home/bautista/C/jetgoBack')

# Configurar variables de entorno
os.environ['SUPABASE_URL'] = 'https://pamidjksvzshakzkrtdy.supabase.co'
os.environ['SUPABASE_ANON_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBhbWlkamtzdnpzaGFremtydGR5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTM3ODgzODMsImV4cCI6MjA2OTM2NDM4M30.sjYTaPhMNymAiJI63Ia9Z7i9ur6izKqRawpkNBSEJdw'

from supabase import create_client, Client

def test_avatar_functionality():
    try:
        # Crear cliente
        url = os.environ.get('SUPABASE_URL')
        key = os.environ.get('SUPABASE_ANON_KEY')
        
        supabase: Client = create_client(url, key)
        
        print("🔍 Verificando bucket 'avatars'...")
        
        # Listar buckets
        try:
            buckets = supabase.storage.list_buckets()
            print(f"📦 Buckets disponibles: {[b.name for b in buckets]}")
            
            # Verificar si existe el bucket avatars
            avatars_bucket = None
            for bucket in buckets:
                if bucket.name == 'avatars':
                    avatars_bucket = bucket
                    break
            
            if avatars_bucket:
                print("✅ Bucket 'avatars' encontrado")
                print(f"   - Público: {avatars_bucket.public}")
                print(f"   - Límite de archivo: {avatars_bucket.file_size_limit}")
                print(f"   - Tipos MIME permitidos: {avatars_bucket.allowed_mime_types}")
            else:
                print("❌ Bucket 'avatars' NO encontrado")
                print("💡 Necesitas crear el bucket manualmente en Supabase Dashboard")
                return False
                
        except Exception as e:
            print(f"❌ Error listando buckets: {e}")
            return False
        
        # Probar subida de archivo
        print("\n🧪 Probando subida de archivo...")
        try:
            test_content = b"test image content"
            test_path = "test-avatar.jpg"
            
            result = supabase.storage.from_('avatars').upload(test_path, test_content)
            print(f"✅ Subida exitosa: {result}")
            
            # Obtener URL pública
            url_data = supabase.storage.from_('avatars').get_public_url(test_path)
            print(f"🔗 URL pública: {url_data}")
            
            # Eliminar archivo de prueba
            supabase.storage.from_('avatars').remove([test_path])
            print("🗑️  Archivo de prueba eliminado")
            
        except Exception as e:
            print(f"❌ Error en subida: {e}")
            return False
        
        print("\n✅ Todas las pruebas pasaron")
        return True
        
    except Exception as e:
        print(f"❌ Error general: {e}")
        return False

if __name__ == "__main__":
    success = test_avatar_functionality()
    sys.exit(0 if success else 1)
