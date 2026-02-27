@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

echo ============================================
echo   Sistema Rampazzo - Build + ZIP
echo ============================================
echo.

:: -----------------------------------------------------------
:: 1. Verificar que estamos en la raiz del proyecto
:: -----------------------------------------------------------
if not exist "main.py" (
    echo [ERROR] No se encontro main.py. Ejecutar este script desde la raiz del proyecto.
    goto :fail
)

if not exist "SistemaRampazzo.spec" (
    echo [ERROR] No se encontro SistemaRampazzo.spec. Es necesario para el build.
    goto :fail
)

:: -----------------------------------------------------------
:: 2. Activar entorno virtual (si existe)
:: -----------------------------------------------------------
echo [1/6] Configurando entorno Python...

if exist ".venv\Scripts\activate.bat" (
    echo       Activando .venv
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    echo       Activando venv
    call venv\Scripts\activate.bat
) else (
    echo       No se encontro .venv ni venv, usando Python del sistema/Anaconda
)

python --version
echo.

:: -----------------------------------------------------------
:: 3. Verificar PyInstaller
:: -----------------------------------------------------------
echo [2/6] Verificando PyInstaller...

pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo       No encontrado. Instalando...
    pip install pyinstaller
    if errorlevel 1 (
        echo [ERROR] No se pudo instalar PyInstaller.
        goto :fail
    )
)
echo       OK
echo.

:: -----------------------------------------------------------
:: 4. Limpiar build anterior
:: -----------------------------------------------------------
echo [3/6] Limpiando build anterior...

:: Intentar limpiar carpetas viejas (build_out y dist_out)
if exist "build_out" rmdir /s /q "build_out" 2>nul
if exist "dist_out" rmdir /s /q "dist_out" 2>nul

:: Verificar que se pudieron limpiar
if exist "dist_out\SistemaRampazzo" (
    echo [ERROR] No se pudo eliminar dist_out\ de un build anterior.
    echo         Cerrar cualquier terminal o explorador que tenga abierta esa carpeta.
    goto :fail
)

echo       OK
echo.

:: -----------------------------------------------------------
:: 5. Incrementar numero de build y generar build_info.py
:: -----------------------------------------------------------
echo [4/6] Incrementando numero de build...

set "BUILD_NUM=0"
if exist "build_number.txt" (
    set /p BUILD_NUM=<build_number.txt
)
set /a BUILD_NUM=!BUILD_NUM! + 1

:: Guardar nuevo numero en build_number.txt
echo !BUILD_NUM!> build_number.txt

:: Obtener timestamp actual via PowerShell (compatible con Windows 10/11)
for /f "usebackq delims=" %%d in (`powershell -NoProfile -Command "Get-Date -Format 'yyyy-MM-dd HH:mm:ss'"`) do set "BUILD_TS=%%d"

:: Generar build_info.py
(
    echo BUILD_NUMBER = !BUILD_NUM!
    echo BUILD_TIMESTAMP = "!BUILD_TS!"
)> build_info.py

echo       Build #!BUILD_NUM! - !BUILD_TS!
echo.

:: -----------------------------------------------------------
:: 6. Compilar con PyInstaller
:: -----------------------------------------------------------
echo [5/6] Compilando ejecutable con PyInstaller...
echo       (esto puede tardar unos minutos)
echo.

:: Agregar PySide6 al PATH para que PyInstaller pueda resolver las DLLs de Qt
for /f "usebackq delims=" %%p in (`python -c "import os, PySide6; print(os.path.dirname(PySide6.__file__))"`) do set "PATH=%%p;!PATH!"

pyinstaller SistemaRampazzo.spec --noconfirm --distpath dist_out --workpath build_out
if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller fallo. Revisar los mensajes de error arriba.
    goto :fail
)
echo.

:: Verificar que se genero el exe
if not exist "dist_out\SistemaRampazzo\SistemaRampazzo.exe" (
    echo [ERROR] No se genero el ejecutable en dist_out\SistemaRampazzo\
    goto :fail
)

:: -----------------------------------------------------------
:: 7. Copiar configuracion y generar ZIP
:: -----------------------------------------------------------
echo [6/6] Generando ZIP distribuible...

:: Copiar config.ini con credenciales reales (para que el exe conecte a MongoDB)
if exist "config.ini" (
    copy /y "config.ini" "dist_out\SistemaRampazzo\config.ini" >nul
    echo       config.ini copiado (con credenciales de MongoDB)
) else (
    echo [WARN] No se encontro config.ini - el ejecutable arrancara en modo offline.
    echo        Copiar config.ini junto al .exe antes de distribuir.
)

:: Copiar plantilla como referencia
copy /y "config.ini.example" "dist_out\SistemaRampazzo\config.ini.example" >nul 2>nul

:: Eliminar ZIP anterior si existe (en raiz del proyecto)
if exist "SistemaRampazzo.zip" del /f "SistemaRampazzo.zip"

:: Crear ZIP usando PowerShell (disponible en Windows 10+)
powershell -NoProfile -Command "Compress-Archive -Path 'dist_out\SistemaRampazzo\*' -DestinationPath 'SistemaRampazzo.zip' -CompressionLevel Optimal"
if errorlevel 1 (
    echo [ERROR] No se pudo crear el ZIP. Verificar que PowerShell esta disponible.
    goto :fail
)

:: -----------------------------------------------------------
:: Resultado
:: -----------------------------------------------------------
echo.
echo ============================================
echo   BUILD EXITOSO
echo ============================================
echo.
echo   Ejecutable: dist_out\SistemaRampazzo\SistemaRampazzo.exe
echo   ZIP:        SistemaRampazzo.zip
echo   Build:      #!BUILD_NUM!
echo.

:: Mostrar tamano del ZIP
for %%A in ("SistemaRampazzo.zip") do (
    set "size=%%~zA"
    set /a "sizeMB=!size! / 1048576"
    echo   Tamano ZIP: ~!sizeMB! MB
)

echo.
echo   Listo para distribuir.
echo ============================================
goto :end

:fail
echo.
echo ============================================
echo   BUILD FALLIDO - Revisar errores arriba
echo ============================================
pause
exit /b 1

:end
pause
endlocal
