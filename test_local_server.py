#!/usr/bin/env python3
"""
Script para probar el servidor local
"""
import requests
import io

# Crear un archivo de audio fake (solo para probar)
fake_audio_content = b"fake audio content for testing"

# Crear FormData
files = {
    'file': ('test_audio.webm', fake_audio_content, 'audio/webm;codecs=opus')
}

data = {
    'user_id': '0f299c7a-cf51-4f3c-aa89-01c3d8533597',
    'room_id': '51f08343-64f0-4abe-839a-b27d9dd1d4a1'
}

# Probar endpoint local
print("Testing LOCAL server...")
try:
    response = requests.post(
        'http://localhost:8000/api/chat/upload-file/',
        files=files,
        data=data
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
except requests.exceptions.ConnectionError:
    print("❌ No se puede conectar al servidor local")
    print("Asegúrate de que el servidor Django esté corriendo en localhost:8000")
except Exception as e:
    print(f"Error: {e}")
