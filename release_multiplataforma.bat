@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>nul

echo ============================================
echo   Sistema Rampazzo - Release Multiplataforma
echo ============================================
echo.

set "VERSION=%~1"
set "REPO=%~2"
set "BRANCH=%~3"

if "%VERSION%"=="" (
  set /p VERSION="Ingrese version (ej: 1.6.1) o ENTER para usar la actual: "
)
if "%REPO%"=="" (
  set /p REPO="Ingrese repo (owner/repo) o ENTER para autodetectar: "
)
if "%BRANCH%"=="" (
  set /p BRANCH="Ingrese rama o ENTER para autodetectar: "
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0release_multiplataforma.ps1" -Version "%VERSION%" -Repo "%REPO%" -Branch "%BRANCH%"

echo.
if %errorlevel%==0 (
  echo Release completada correctamente.
) else (
  echo [ERROR] La release termino con codigo %errorlevel%.
)
echo.
pause
exit /b %errorlevel%
