@echo off
setlocal
cd /d %~dp0

echo ==^> Setting up dependencies...
uv sync
if errorlevel 1 (echo uv sync failed. Install uv from https://docs.astral.sh/uv/ & pause & exit /b 1)

echo ==^> Running tests...
uv run --with pytest --with pytest-qt python -m pytest tests/ -v
if errorlevel 1 (echo Tests failed. Fix tests before building. & pause & exit /b 1)

echo ==^> Generating icon...
uv run python scripts\make_icon.py
if errorlevel 1 goto :error

echo ==^> Closing running instances...
taskkill /f /im motion-capture.exe 2>nul
del /f /q dist\motion-capture.exe 2>nul

echo ==^> Building .exe...
uv run pyinstaller motion-capture-windows-x64.spec --clean --noconfirm
if errorlevel 1 goto :error

echo.
echo Done: dist\motion-capture.exe
goto :end

:error
echo.
echo Build failed.
pause
exit /b 1

:end
pause
