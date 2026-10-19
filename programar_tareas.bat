@echo off
REM ---------------------------------------------------------------
REM  Registra DOS tareas en el Programador de tareas de Windows:
REM    - diaria  (07:00): cargar_diario.bat   -> incremental por términos
REM    - semanal (dom 03:00): cargar_semanal.bat -> catálogo completo
REM  Uso:  programar_tareas.bat
REM  Quitar:
REM    schtasks /Delete /TN "precios-supermercados-etl diario" /F
REM    schtasks /Delete /TN "precios-supermercados-etl semanal" /F
REM  Requiere sesion con permiso (probablemente admin).
REM ---------------------------------------------------------------
setlocal
chcp 65001 >nul
cd /d "%~dp0"

schtasks /Create /TN "precios-supermercados-etl diario" /TR "\"%~dp0cargar_diario.bat\"" /SC DAILY /ST 07:00 /F
set RC1=%errorlevel%
schtasks /Create /TN "precios-supermercados-etl semanal" /TR "\"%~dp0cargar_semanal.bat\"" /SC WEEKLY /D SUN /ST 03:00 /F
set RC2=%errorlevel%

echo.
if "%RC1%%RC2%"=="00" (
    echo [OK] tareas creadas: diaria 07:00 + semanal domingo 03:00.
) else (
    echo [AVISO] alguna tarea fallo ^(diario=%RC1% semanal=%RC2%^). Proba "Ejecutar como administrador".
)
echo Ver:   schtasks /Query /TN "precios-supermercados-etl diario"
echo        schtasks /Query /TN "precios-supermercados-etl semanal"
pause
endlocal & exit /b 0
