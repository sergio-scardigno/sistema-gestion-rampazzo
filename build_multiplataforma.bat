@echo off
setlocal EnableExtensions

chcp 65001 >nul 2>nul

echo ============================================
echo   Sistema Rampazzo - Build Multiplataforma
echo   (orquestado con GitHub Actions)
echo ============================================
echo.

set "VERSION=%~1"
set "REPO=%~2"
set "BRANCH=%~3"

if "%VERSION%"=="" (
  set /p VERSION="Ingrese la version (ej: 1.2.0): "
)
if "%VERSION%"=="" (
  echo [ERROR] No se ingreso una version.
  pause
  exit /b 1
)

if "%REPO%"=="" (
  set /p REPO="Ingrese el repositorio (ej: usuario/repo) o ENTER para autodetectar: "
)

if "%BRANCH%"=="" (
  set /p BRANCH="Ingrese la rama (ej: main) o ENTER para usar main: "
)
if "%BRANCH%"=="" set "BRANCH=main"

set "PS_SCRIPT=%~dp0build_multiplataforma.ps1"
if not exist "%PS_SCRIPT%" (
  echo [ERROR] No se encontro %PS_SCRIPT%
  pause
  exit /b 1
)

echo.
echo   Version: %VERSION%
echo   Repo:    %REPO%
echo   Rama:    %BRANCH%
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%" -Version "%VERSION%" -Repo "%REPO%" -Branch "%BRANCH%"

echo.
if %errorlevel%==0 (
  echo Proceso completado exitosamente.
) else (
  echo [ERROR] El proceso termino con codigo %errorlevel%.
)
echo.
pause
exit /b %errorlevel%
