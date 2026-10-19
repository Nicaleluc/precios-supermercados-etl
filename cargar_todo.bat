@echo off
REM ---------------------------------------------------------------
REM  Carga completa: precios + sucursales (precios-supermercados-etl)
REM  Doble clic, o:  cargar_todo.bat [flags de importar_precios]
REM  Ej:  cargar_todo.bat --cadena vea --termino leche
REM       cargar_todo.bat --catalogo            (todo el catalogo VTEX)
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

echo == Precios ==
%PY% -u -m cli.importar_precios %*
set RC=%errorlevel%

echo.
echo == Sucursales ==
%PY% -u -m cli.cargar_sucursales
if not "%RC%"=="0" set RC=%errorlevel%

echo.
if not "%RC%"=="0" echo [ERROR] termino con codigo %RC%.
pause
endlocal & exit /b %RC%
