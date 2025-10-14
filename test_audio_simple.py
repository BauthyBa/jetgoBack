#!/usr/bin/env python3
"""
Script simple para probar la subida de audio
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

# Probar endpoint de prueba
print("Testing test-audio endpoint...")
response = requests.post(
    'https://jetgoback.onrender.com/api/chat/test-audio/',
    files=files,
    data=data
)

print(f"Status: {response.status_code}")
print(f"Response: {response.text}")

# Probar endpoint real
print("\nTesting upload-file endpoint...")
response2 = requests.post(
    'https://jetgoback.onrender.com/api/chat/upload-file/',
    files=files,
    data=data
)

print(f"Status: {response2.status_code}")
print(f"Response: {response2.text}")
