@echo off
title GEIIA ARCADE - Instalacion
cd /d "%~dp0"

echo.
echo  === GEIIA ARCADE - instalacion en esta computadora ===
echo.

where python >nul 2>nul
if errorlevel 1 goto nopython

echo [1/3] Creando entorno virtual...
python -m venv .venv
if errorlevel 1 goto nopython

echo [2/3] Actualizando pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet

echo [3/3] Instalando dependencias (tarda unos minutos)...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto fallo

echo.
echo  ==========================================
echo   LISTO. Abre INICIAR.bat para jugar.
echo  ==========================================
pause
exit /b 0

:nopython
echo.
echo  No se encontro Python en esta computadora.
echo  Instalalo desde https://www.python.org/downloads/
echo  IMPORTANTE: marca la casilla "Add Python to PATH" al instalar.
echo.
pause
exit /b 1

:fallo
echo.
echo  Fallo la instalacion de dependencias.
echo  Revisa que tengas internet y vuelve a intentar.
echo.
pause
exit /b 1
