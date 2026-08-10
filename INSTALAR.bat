@echo off
setlocal enabledelayedexpansion
title GEIIA ARCADE - Instalacion
cd /d "%~dp0"

echo.
echo   ============================================
echo    GEIIA ARCADE - instalacion
echo   ============================================
echo.

rem ---------------------------------------------------------------
rem  Buscar un Python que SIRVA.
rem
rem  Windows 11 trae un "python.exe" falso en WindowsApps que solo
rem  abre la Microsoft Store. Si el usuario instalo Python sin marcar
rem  "Add to PATH", ese impostor gana y el mensaje que sale no tiene
rem  nada que ver con el problema real. Por eso probamos ejecutando
rem  de verdad, no solo viendo si el comando existe.
rem ---------------------------------------------------------------
set PY=

rem 1) El lanzador oficial de Windows: es el mas confiable
py -3 -c "import sys" >nul 2>nul && set PY=py -3

rem 2) El python del PATH (aqui se cae si es el impostor de la Store)
if not defined PY (
    python -c "import sys" >nul 2>nul && set PY=python
)

rem 3) Instalaciones tipicas, por si no quedo en el PATH
if not defined PY (
    for %%D in (
        "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
        "%ProgramFiles%\Python313\python.exe"
        "%ProgramFiles%\Python312\python.exe"
        "%ProgramFiles%\Python311\python.exe"
        "%ProgramFiles%\Python310\python.exe"
    ) do (
        if not defined PY if exist %%D set PY=%%D
    )
)

if not defined PY goto sinpython

for /f "tokens=*" %%V in ('%PY% -c "import sys;print(sys.version.split()[0])"') do set VER=%%V
echo   Python encontrado: !VER!

%PY% -c "import sys;sys.exit(0 if sys.version_info>=(3,10) else 1)"
if errorlevel 1 goto viejo

echo.
echo   [1/3] Creando entorno virtual...
if exist ".venv" (
    echo         ya existia, lo reutilizo
) else (
    %PY% -m venv .venv
    if errorlevel 1 goto fallovenv
)

echo   [2/3] Actualizando pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet

echo   [3/3] Instalando dependencias ^(tarda unos minutos^)...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto fallodeps

echo.
echo   Comprobando que todo cargue...
".venv\Scripts\python.exe" -c "import pygame,cv2,mediapipe,numpy,customtkinter" 2>nul
if errorlevel 1 goto fallodeps

echo.
echo   ============================================
echo    LISTO. Abre INICIAR.bat para jugar.
echo   ============================================
echo.
echo   Si algo falla, corre:  DIAGNOSTICO.bat
echo.
pause
exit /b 0

:sinpython
echo.
echo   No encontre Python en esta computadora.
echo.
echo   1. Descargalo de https://www.python.org/downloads/
echo   2. IMPORTANTE: al instalar, marca la casilla
echo      "Add Python to PATH" ^(abajo del todo^)
echo   3. Cierra esta ventana y vuelve a abrir INSTALAR.bat
echo.
echo   Si YA lo instalaste y aun asi ves esto, es porque
echo   Windows esta usando su version falsa de la Store:
echo   ve a Configuracion ^> Aplicaciones ^> Configuracion
echo   avanzada ^> Alias de ejecucion, y APAGA python.exe
echo.
pause
exit /b 1

:viejo
echo.
echo   Tu version de Python ^(!VER!^) es muy vieja.
echo   Se necesita 3.10 o mas nueva.
echo   Descarga la ultima de https://www.python.org/downloads/
echo.
pause
exit /b 1

:fallovenv
echo.
echo   No pude crear el entorno virtual.
echo   Prueba mover la carpeta a una ruta sin acentos ni
echo   espacios raros, por ejemplo C:\GEIIA-ARCADE
echo.
pause
exit /b 1

:fallodeps
echo.
echo   Fallo la instalacion de dependencias.
echo   Revisa que tengas internet y vuelve a intentar.
echo   Si sigue fallando, corre DIAGNOSTICO.bat y manda
echo   lo que aparezca.
echo.
pause
exit /b 1
