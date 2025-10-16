#!/bin/bash

# Script de deployment para JetGo Backend
echo "🚀 Starting JetGo Backend deployment..."

# Check if we're in the right directory
if [ ! -f "manage.py" ]; then
    echo "❌ Error: manage.py not found. Are you in the correct directory?"
    exit 1
fi

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Check environment variables
echo "🔍 Checking environment variables..."
python check_env.py

# Run database migrations
echo "🗄️ Running database migrations..."
python manage.py migrate

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput

# Test connection
echo "🧪 Testing backend connection..."
python test_connection.py

echo "✅ Deployment completed successfully!"
echo "🌐 Backend should be available at: https://jetgo-back.onrender.com"