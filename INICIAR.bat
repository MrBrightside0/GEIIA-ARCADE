@echo off
title GEIIA ARCADE
cd /d "%~dp0"

set PY=python
if exist ".venv\Scripts\python.exe" set PY=.venv\Scripts\python.exe

"%PY%" main_menu.py

if errorlevel 1 (
  echo.
  echo ============================================
  echo  El arcade se cerro con un error.
  echo  Si dice "No module named ...", corre
  echo  INSTALAR.bat una vez y vuelve a intentar.
  echo ============================================
  pause
)
