@echo off
setlocal

echo =^=> Setting up dependencies...
uv sync
if errorlevel 1 (echo uv sync failed. Install uv from https://docs.astral.sh/uv/ & pause & exit /b 1)
uv add pyinstaller pynput
if errorlevel 1 goto :error

echo =^=> Running tests...
uv run --with pytest --with pytest-qt python -m pytest tests/ -v
if errorlevel 1 (echo Tests failed. Fix tests before building. & pause & exit /b 1)

echo =^=> Generating icon...
uv run python scripts\make_icon.py
if errorlevel 1 goto :error

echo =^=> Generating sound...
uv run python scripts\make_sound.py
if errorlevel 1 goto :error

echo =^=> Closing running instances...
taskkill /f /im auto-clicker.exe 2>nul
del /f /q dist\auto-clicker.exe 2>nul

echo =^=> Building .exe...
uv run pyinstaller auto-clicker-windows.spec --clean --noconfirm
if errorlevel 1 goto :error

echo.
echo Done: dist\auto-clicker.exe
goto :end

:error
echo.
echo Build failed.
pause
exit /b 1

:end
pause
