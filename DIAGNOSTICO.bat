@echo off
title GEIIA ARCADE - Diagnostico
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" DIAGNOSTICO.py %*
) else (
    echo.
    echo   Todavia no esta instalado. Abre INSTALAR.bat primero.
    echo.
)

echo.
pause
