@echo off
REM ---------------------------------------------------------------
REM  Carga diaria headless: precios + sucursales + SEPA.
REM  SIN pause (para Task Scheduler). Logs en logs\
REM  (precios-supermercados-etl)
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

echo [%date% %time%] inicio precios >> "%~dp0logs\carga.log"
%PY% -u -m cli.importar_precios %* >> "%~dp0logs\carga.log" 2>&1
%PY% -u -m cli.cargar_sucursales >> "%~dp0logs\carga.log" 2>&1
echo [%date% %time%] fin precios >> "%~dp0logs\carga.log"

echo [%date% %time%] inicio sepa >> "%~dp0logs\sepa.log"
%PY% -u -m cli.cargar_sepa --auto >> "%~dp0logs\sepa.log" 2>&1
echo [%date% %time%] fin sepa >> "%~dp0logs\sepa.log"

endlocal & exit /b 0
