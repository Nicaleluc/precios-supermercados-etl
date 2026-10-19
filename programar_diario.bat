@echo off
REM ---------------------------------------------------------------
REM  Registra una tarea DIARIA en el Programador de tareas de Windows
REM  que corre cargar_diario.bat (precios + sucursales).
REM  Uso:  programar_diario.bat [HH:MM]      (default 07:00)
REM  Quitar:  schtasks /Delete /TN "precios-supermercados-etl" /F
REM  Requiere sesion con permiso (probablemente admin).
REM ---------------------------------------------------------------
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set HORA=%~1
if "%HORA%"=="" set HORA=07:00

schtasks /Create /TN "precios-supermercados-etl" /TR "\"%~dp0cargar_diario.bat\"" /SC DAILY /ST %HORA% /F
set RC=%errorlevel%
echo.
if "%RC%"=="0" (
    echo [OK] tarea "precios-supermercados-etl" programada a las %HORA%.
) else (
    echo [ERROR] no se pudo crear la tarea (codigo %RC%). Proba "Ejecutar como administrador".
    echo Manual:  schtasks /Create /TN "precios-supermercados-etl" /TR "\"%~dp0cargar_diario.bat\"" /SC DAILY /ST %HORA% /F
)
pause
endlocal & exit /b %RC%
