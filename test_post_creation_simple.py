#!/usr/bin/env python
"""
Script simple para probar creación de posts
"""

import requests
import json

def test_post_creation():
    """Probar creación de posts sin archivo"""
    base_url = "http://localhost:8000/api/social"
    
    # Datos de prueba para el post (sin archivo)
    post_data = {
        'user_id': '00000000-0000-0000-0000-000000000001',  # Usuario de prueba
        'content': '¡Mi primer post desde el script de prueba! 🚀',
        'location': 'Buenos Aires, Argentina',
        'is_public': 'true'
    }
    
    print("🔍 Probando creación de post (sin archivo)...")
    print(f"URL: {base_url}/posts/")
    print(f"Datos: {post_data}")
    
    try:
        # Probar POST
        post_response = requests.post(f"{base_url}/posts/", data=post_data)
        print(f"POST Status: {post_response.status_code}")
        
        if post_response.status_code == 200:
            data = post_response.json()
            print(f"✅ Post creado exitosamente: {data}")
        else:
            print(f"❌ Error POST: {post_response.text}")
        
        # Probar GET después del POST
        print("\n📥 Probando GET posts después del POST...")
        get_response = requests.get(f"{base_url}/posts/")
        print(f"GET Status: {get_response.status_code}")
        
        if get_response.status_code == 200:
            data = get_response.json()
            print(f"Posts encontrados: {len(data.get('posts', []))}")
            if data.get('posts'):
                print(f"Primer post: {data['posts'][0]['content']}")
        else:
            print(f"Error GET: {get_response.text}")
            
    except Exception as e:
        print(f"❌ Error en la prueba: {e}")

def test_stories():
    """Probar stories"""
    base_url = "http://localhost:8000/api/social"
    
    print("\n🔍 Probando stories...")
    
    try:
        response = requests.get(f"{base_url}/stories/")
        print(f"Stories Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Stories encontradas: {len(data.get('stories', []))}")
        else:
            print(f"Error Stories: {response.text}")
            
    except Exception as e:
        print(f"❌ Error en stories: {e}")

if __name__ == "__main__":
    print("🚀 Iniciando pruebas de API social...")
    test_post_creation()
    test_stories()
    print("\n🎉 Pruebas completadas!")

