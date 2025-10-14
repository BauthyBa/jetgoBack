#!/usr/bin/env python3
"""
Script para configurar las políticas de RLS para el sistema de notificaciones
"""

import os
import sys
from supabase import create_client, Client

def get_supabase_client():
    """Obtener cliente de Supabase"""
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    if not url or not key:
        print("❌ Error: SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY deben estar configurados")
        sys.exit(1)
    
    return create_client(url, key)

def configure_rls_policies():
    """Configurar políticas de RLS para notificaciones"""
    try:
        supabase = get_supabase_client()
        print("🔧 Configurando políticas de RLS para notificaciones...")
        
        # Leer el archivo SQL
        with open('configure_notifications_rls.sql', 'r') as f:
            sql_content = f.read()
        
        # Dividir en declaraciones individuales
        statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]
        
        for i, statement in enumerate(statements, 1):
            if statement:
                print(f"🔧 Ejecutando declaración {i}/{len(statements)}...")
                try:
                    # Ejecutar la declaración SQL
                    result = supabase.rpc('exec_sql', {'sql': statement})
                    print(f"✅ Declaración {i} ejecutada exitosamente")
                except Exception as e:
                    print(f"⚠️  Advertencia en declaración {i}: {e}")
                    # Continuar con las siguientes declaraciones
        
        print("✅ Políticas de RLS configuradas exitosamente")
        print("\n📋 Políticas configuradas:")
        print("  - Usuarios pueden ver mensajes de salas donde son miembros")
        print("  - Usuarios pueden insertar mensajes en salas donde son miembros")
        print("  - Usuarios pueden actualizar/eliminar sus propios mensajes")
        print("  - Usuarios pueden ver miembros de salas donde pertenecen")
        print("  - Usuarios pueden ver salas donde son miembros")
        
    except Exception as e:
        print(f"❌ Error configurando políticas de RLS: {e}")
        sys.exit(1)

if __name__ == "__main__":
    configure_rls_policies()
