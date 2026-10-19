@echo off
REM ---------------------------------------------------------------
REM  Descarga y carga SEPA del dia (precios por sucursal).
REM  Sin pause (para Task Scheduler). Log en logs\sepa.log
REM  Doble clic para correr una vez a mano.
REM ---------------------------------------------------------------
setlocal
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

set PY=py
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
    set PY=python
) else (
    where py >nul 2>nul || set PY=python
)

if not exist "logs" mkdir "logs"
set LOG=%~dp0logs\sepa.log

echo [%date% %time%] inicio sepa >> "%LOG%"
%PY% -u -m cli.cargar_sepa --auto %* >> "%LOG%" 2>&1
echo [%date% %time%] fin sepa >> "%LOG%"

endlocal & exit /b 0
