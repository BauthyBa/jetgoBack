#!/usr/bin/env python3
"""
Script para probar localmente
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.settings')
django.setup()

from trips.chat_views import ALLOWED_FILE_TYPES
from django.core.files.uploadedfile import SimpleUploadedFile

# Crear un archivo fake
fake_content = b"fake audio content"
fake_file = SimpleUploadedFile(
    "test.webm",
    fake_content,
    content_type="audio/webm;codecs=opus"
)

print(f"File content_type: {fake_file.content_type}")
print(f"File size: {fake_file.size}")
print(f"Is audio: {fake_file.content_type.startswith('audio/')}")
print(f"Allowed types: {ALLOWED_FILE_TYPES}")
print(f"Type in allowed: {fake_file.content_type in ALLOWED_FILE_TYPES}")

# Simular validación
is_audio_file = fake_file.content_type.startswith('audio/')
if is_audio_file:
    print("Audio file detected - would be accepted")
else:
    print("Not an audio file")
