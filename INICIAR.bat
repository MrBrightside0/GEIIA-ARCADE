@echo off
title GEIIA ARCADE
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" goto sinvenv

rem Se usa python.exe y no pythonw.exe a proposito: deja esta consola
rem abierta detras del arcade, y si algo truena el error queda a la vista
rem en lugar de que la ventana simplemente no aparezca.
rem
rem Tampoco se usan timeout, find ni tasklist: si la computadora tiene Git
rem Bash en el PATH, esos nombres los toman las versiones de Unix y el
rem script falla por algo que no tiene nada que ver con el juego.

".venv\Scripts\python.exe" main_menu.py

if errorlevel 1 (
    echo.
    echo   ============================================
    echo    El arcade se cerro con un error.
    echo   ============================================
    echo.
    echo   Si dice "No module named ...", corre
    echo   INSTALAR.bat una vez y vuelve a intentar.
    echo.
    echo   Para una revision completa: DIAGNOSTICO.bat
    echo.
    pause
)
exit /b 0

:sinvenv
echo.
echo   ============================================
echo    Falta instalar el arcade en esta compu.
echo   ============================================
echo.
echo   Abre INSTALAR.bat una vez ^(tarda unos minutos^)
echo   y despues ya puedes usar este archivo siempre.
echo.
pause
exit /b 1
