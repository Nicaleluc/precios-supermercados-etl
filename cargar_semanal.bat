@echo off
REM ---------------------------------------------------------------
REM  Carga SEMANAL de catalogo completo (precios + sucursales).
REM  Sin pause (para Task Scheduler). Log en logs\catalogo.log
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
set LOG=%~dp0logs\catalogo.log

echo [%date% %time%] inicio catalogo >> "%LOG%"
%PY% -u -m cli.importar_precios --catalogo --cat-paginas 10 %* >> "%LOG%" 2>&1
%PY% -u -m cli.cargar_sucursales >> "%LOG%" 2>&1
echo [%date% %time%] fin >> "%LOG%"

endlocal & exit /b 0
