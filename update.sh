#!/usr/bin/env bash
# Hermes HUD Web UI — Update & Rebuild script
# Use this to reflect changes after pulling code
set -e

echo "☤ Hermes HUD — Updating Changes"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Verification of environment
if [ ! -d "venv" ]; then
    echo "✗ Error: venv not found. Please run ./install.sh first."
    exit 1
fi

# 2. Cleaning Cache and Build Artifacts
echo "→ Cleaning old build files and caches..."
rm -rf frontend/dist
rm -rf frontend/node_modules/.vite
rm -rf backend/static/*
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
echo "✔ Cache cleared"

# 3. Refreshing Backend Installation
echo "→ Refreshing backend installation..."
source venv/bin/activate
pip install -e . -q
echo "✔ Backend refreshed"

# 4. Rebuilding Frontend
echo "→ Building frontend (this may take a moment)..."
cd frontend
npm install --silent
npm run build
cd ..
echo "✔ Frontend built"

# 5. Deploying to Backend Static Directory
echo "→ Deploying to backend..."
mkdir -p backend/static
cp -r frontend/dist/* backend/static/
echo "✔ Deployment complete"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✔ Success! Your changes are now live."
echo "  Run with: hermes-hudui"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
