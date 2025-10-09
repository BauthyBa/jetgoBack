#!/usr/bin/env python3
"""
Script para ejecutar la migración de avatar_url en Supabase
"""
import os
import sys
from supabase import create_client, Client

def main():
    # Configuración de Supabase
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not key:
        print("❌ Error: SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY deben estar configurados")
        sys.exit(1)
    
    # Crear cliente de Supabase
    supabase: Client = create_client(url, key)
    
    print("🚀 Iniciando migración de avatar_url...")
    
    try:
        # 1. Ejecutar script SQL para agregar columna y sincronizar datos
        with open('supabase/add_avatar_url_column.sql', 'r') as f:
            sql_script = f.read()
        
        print("📝 Ejecutando script SQL...")
        result = supabase.rpc('exec_sql', {'sql': sql_script}).execute()
        
        if result.data:
            print("✅ Script SQL ejecutado exitosamente")
        else:
            print("⚠️  Script SQL ejecutado, pero sin datos de retorno")
        
        # 2. Verificar que la columna existe
        print("🔍 Verificando columna avatar_url...")
        test_result = supabase.table('User').select('userid,avatar_url').limit(1).execute()
        
        if test_result.data:
            print("✅ Columna avatar_url agregada exitosamente")
            print(f"📊 Ejemplo de datos: {test_result.data[0]}")
        else:
            print("❌ Error: No se pudo verificar la columna")
            
    except Exception as e:
        print(f"❌ Error durante la migración: {str(e)}")
        sys.exit(1)
    
    print("🎉 Migración completada exitosamente!")

if __name__ == "__main__":
    main()
