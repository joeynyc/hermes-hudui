#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
STATIC_DIR="$PROJECT_ROOT/backend/static"

cd "$FRONTEND_DIR"
npm ci
npm run build

mkdir -p "$STATIC_DIR"
rm -rf "$STATIC_DIR/assets"
cp -R "$FRONTEND_DIR/dist/." "$STATIC_DIR/"
