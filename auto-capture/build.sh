#!/bin/bash
set -e

echo "==> Generating icon..."
.venv/bin/python scripts/make_icon.py

echo "==> Generating sound..."
.venv/bin/python scripts/make_sound.py

echo "==> Building .app bundle..."
.venv/bin/pyinstaller ticketure.spec --clean --noconfirm

echo ""
echo "Done: dist/ticketure.app"
