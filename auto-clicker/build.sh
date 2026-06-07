#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "==> Generating icon..."
uv run --package auto-clicker python scripts/make_icon.py

echo "==> Generating sound..."
uv run --package auto-clicker python scripts/make_sound.py

echo "==> Building .app bundle..."
uv run --package auto-clicker pyinstaller auto-clicker.spec --clean --noconfirm

echo ""
echo "Done: dist/auto-clicker.app"
