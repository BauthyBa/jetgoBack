#!/bin/bash
echo "Deploying to Render..."

# Commit changes
git add .
git commit -m "Fix audio upload validation - accept all audio types"

# Push to main branch
git push origin main

echo "Deployment initiated. Check Render dashboard for status."
