#!/usr/bin/env python3
"""
Script para probar endpoint simple
"""
import requests

# Probar endpoint simple GET
print("Testing simple GET endpoint...")
try:
    response = requests.get('http://localhost:8000/api/chat/test/')
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "="*50 + "\n")

# Probar endpoint de prueba de audio
print("Testing test-audio endpoint...")
try:
    fake_content = b"fake audio content"
    files = {
        'file': ('test.webm', fake_content, 'audio/webm;codecs=opus')
    }
    
    response = requests.post(
        'http://localhost:8000/api/chat/test-audio/',
        files=files
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
except Exception as e:
    print(f"Error: {e}")
