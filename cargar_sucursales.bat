@echo off
REM ---------------------------------------------------------------
REM  Carga de sucursales -> D_PrecioSucursal (precios-supermercados-etl)
REM  Doble clic, o:  cargar_sucursales.bat [--sin-coope]
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

%PY% -u -m cli.cargar_sucursales %*
set RC=%errorlevel%
echo.
if not "%RC%"=="0" echo [ERROR] termino con codigo %RC%.
pause
endlocal & exit /b %RC%
