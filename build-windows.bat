@echo off
setlocal

echo =^=> Setting up dependencies...
uv sync
if errorlevel 1 (echo uv not found. Install from https://docs.astral.sh/uv/ & pause & exit /b 1)
uv add pyinstaller
if errorlevel 1 goto :error

echo =^=> Generating icon...
.venv\Scripts\python.exe scripts\make_icon.py
if errorlevel 1 goto :error

echo =^=> Building .exe...
.venv\Scripts\pyinstaller.exe ticketure-windows.spec --clean --noconfirm
if errorlevel 1 goto :error

echo.
echo Done: dist\ticketure.exe
goto :end

:error
echo.
echo Build failed.
pause
exit /b 1

:end
pause
