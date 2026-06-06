@echo off
setlocal

echo =^=> Generating icon...
.venv\Scripts\python.exe scripts\make_icon.py
if errorlevel 1 goto :error

echo =^=> Building .exe...
.venv\Scripts\pyinstaller.exe ticketure-windows.spec --clean --noconfirm
if errorlevel 1 goto :error

echo.
echo Done: dist\ticketure\ticketure.exe
goto :end

:error
echo Build failed.
exit /b 1

:end
