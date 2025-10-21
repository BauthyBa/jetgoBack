#!/usr/bin/env python3
"""
Script para probar la conectividad del backend
"""
import os
import sys
import django
from pathlib import Path

# Add the project directory to Python path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.settings')
django.setup()

from django.test import Client
from django.urls import reverse
import json

def test_endpoints():
    """Test all social endpoints"""
    client = Client()
    
    endpoints = [
        '/api/social/test/',
        '/api/social/posts/',
        '/api/social/stories/',
    ]
    
    print("🧪 Testing backend endpoints...")
    
    for endpoint in endpoints:
        try:
            print(f"\n📍 Testing {endpoint}")
            
            # Test GET request
            response = client.get(endpoint)
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"   Response: {json.dumps(data, indent=2)[:200]}...")
                except:
                    print(f"   Response: {response.content[:200]}...")
            else:
                print(f"   Error: {response.content[:200]}")
                
        except Exception as e:
            print(f"   Exception: {e}")
    
    print("\n✅ Test completed!")

def test_supabase_config():
    """Test Supabase configuration"""
    print("\n🔧 Testing Supabase configuration...")
    
    try:
        from api.supabase_client import get_supabase_admin, get_supabase_anon
        
        # Test admin client
        try:
            admin_client = get_supabase_admin()
            print("✅ Supabase admin client: OK")
        except Exception as e:
            print(f"❌ Supabase admin client: {e}")
        
        # Test anon client
        try:
            anon_client = get_supabase_anon()
            print("✅ Supabase anon client: OK")
        except Exception as e:
            print(f"❌ Supabase anon client: {e}")
            
    except Exception as e:
        print(f"❌ Supabase configuration error: {e}")

def test_database_connection():
    """Test database connection"""
    print("\n🗄️ Testing database connection...")
    
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            print("✅ Database connection: OK")
    except Exception as e:
        print(f"❌ Database connection error: {e}")

if __name__ == "__main__":
    print("🚀 Starting backend connectivity tests...")
    
    test_database_connection()
    test_supabase_config()
    test_endpoints()
    
    print("\n🎉 All tests completed!")






