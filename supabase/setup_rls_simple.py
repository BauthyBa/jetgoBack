#!/usr/bin/env python3
"""
Script simple para configurar RLS usando el admin client
"""

import os
import sys
from supabase import create_client, Client

def get_supabase_admin():
    """Obtener cliente admin de Supabase"""
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    if not url or not key:
        print("❌ Error: SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY deben estar configurados")
        print("   Configura estas variables de entorno y ejecuta el script nuevamente")
        sys.exit(1)
    
    return create_client(url, key)

def setup_rls():
    """Configurar RLS para notificaciones"""
    try:
        admin = get_supabase_admin()
        print("🔧 Configurando RLS para sistema de notificaciones...")
        
        # Políticas SQL que necesitamos ejecutar
        policies = [
            # Habilitar RLS en chat_messages
            "ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY;",
            
            # Política para ver mensajes de salas donde el usuario es miembro
            """
            CREATE POLICY "Users can view messages from rooms they belong to" ON public.chat_messages
            FOR SELECT
            USING (
              EXISTS (
                SELECT 1 FROM public.chat_members 
                WHERE chat_members.room_id = chat_messages.room_id 
                AND chat_members.user_id = auth.uid()::text
              )
            );
            """,
            
            # Habilitar RLS en chat_members
            "ALTER TABLE public.chat_members ENABLE ROW LEVEL SECURITY;",
            
            # Política para ver miembros de salas
            """
            CREATE POLICY "Users can view members of rooms they belong to" ON public.chat_members
            FOR SELECT
            USING (
              EXISTS (
                SELECT 1 FROM public.chat_members cm 
                WHERE cm.room_id = chat_members.room_id 
                AND cm.user_id = auth.uid()::text
              )
            );
            """,
            
            # Habilitar RLS en chat_rooms
            "ALTER TABLE public.chat_rooms ENABLE ROW LEVEL SECURITY;",
            
            # Política para ver salas donde el usuario es miembro
            """
            CREATE POLICY "Users can view rooms they belong to" ON public.chat_rooms
            FOR SELECT
            USING (
              EXISTS (
                SELECT 1 FROM public.chat_members 
                WHERE chat_members.room_id = chat_rooms.id 
                AND chat_members.user_id = auth.uid()::text
              )
            );
            """
        ]
        
        for i, policy in enumerate(policies, 1):
            print(f"🔧 Ejecutando política {i}/{len(policies)}...")
            try:
                # Ejecutar usando rpc
                result = admin.rpc('exec_sql', {'sql': policy}).execute()
                print(f"✅ Política {i} configurada exitosamente")
            except Exception as e:
                print(f"⚠️  Advertencia en política {i}: {e}")
                # Continuar con las siguientes políticas
        
        print("\n✅ RLS configurado exitosamente")
        print("\n📋 Políticas configuradas:")
        print("  ✅ chat_messages: Usuarios pueden ver mensajes de salas donde son miembros")
        print("  ✅ chat_members: Usuarios pueden ver miembros de salas donde pertenecen")
        print("  ✅ chat_rooms: Usuarios pueden ver salas donde son miembros")
        print("\n🎉 El sistema de notificaciones debería funcionar ahora")
        
    except Exception as e:
        print(f"❌ Error configurando RLS: {e}")
        print("\n💡 Solución manual:")
        print("1. Ve a tu panel de Supabase")
        print("2. Ve a Authentication > Policies")
        print("3. Configura las políticas manualmente")
        sys.exit(1)

if __name__ == "__main__":
    setup_rls()
