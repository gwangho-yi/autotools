#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "==> Generating icon..."
uv run --package auto-capture python scripts/make_icon.py

echo "==> Generating sound..."
uv run --package auto-capture python scripts/make_sound.py

echo "==> Building .app bundle..."
uv run --package auto-capture pyinstaller auto-capture.spec --clean --noconfirm

echo ""
echo "Done: dist/auto-capture.app"
