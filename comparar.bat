@echo off
REM ---------------------------------------------------------------
REM  Comparador de canasta entre supermercados
REM  (precios-supermercados-etl)
REM
REM  Doble clic, o:  comparar.bat [terminos] [flags]
REM  Ejemplos:
REM    comparar.bat
REM    comparar.bat leche yerba aceite azucar
REM    comparar.bat --cadena vea leche pan
REM  Ver flags:  comparar.bat --help
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

%PY% -u -m cli.comparar %*
set RC=%errorlevel%
echo.
if not "%RC%"=="0" echo [ERROR] La comparacion termino con codigo %RC%.
pause
endlocal & exit /b %RC%
