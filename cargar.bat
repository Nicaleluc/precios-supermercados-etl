@echo off
REM ---------------------------------------------------------------
REM  Extract de precios de supermercados -> store local SQLite
REM  (precios-supermercados-etl)
REM
REM  Doble clic, o:  cargar.bat [flags]
REM  Ejemplos:
REM    cargar.bat
REM    cargar.bat --cadena vea --termino leche --termino yerba
REM    cargar.bat --paginas 3
REM  Ver flags:  cargar.bat --help
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

%PY% -u -m cli.importar_precios %*
set RC=%errorlevel%
echo.
if not "%RC%"=="0" echo [ERROR] La carga termino con codigo %RC%.
pause
endlocal & exit /b %RC%
