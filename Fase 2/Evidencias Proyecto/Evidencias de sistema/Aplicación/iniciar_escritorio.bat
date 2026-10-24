@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem Inicia el cliente local desde cualquier directorio, incluida una ruta de red.
pushd "%~dp0"
if errorlevel 1 (
    echo No se pudo acceder a la carpeta de SIGET.
    exit /b 1
)

set "PYTHON_ARGS="
if exist "..\..\..\..\.venv\Scripts\python.exe" (
    for %%I in ("..\..\..\..\.venv\Scripts\python.exe") do set "PYTHON_EXE=%%~fI"
    goto ejecutar
)
if exist ".venv\Scripts\python.exe" (
    for %%I in (".venv\Scripts\python.exe") do set "PYTHON_EXE=%%~fI"
    goto ejecutar
)
where py.exe >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_EXE=py.exe"
    set "PYTHON_ARGS=-3"
    goto ejecutar
)
where python.exe >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_EXE=python.exe"
    goto ejecutar
)
echo No se encontro Python. Instala Python 3.12 o superior y prepara el entorno virtual.
goto error

:ejecutar
"%PYTHON_EXE%" %PYTHON_ARGS% -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)"
if errorlevel 1 (
    echo SIGET Escritorio requiere Python 3.12 o superior.
    goto error
)
"%PYTHON_EXE%" %PYTHON_ARGS% -c "from PySide6.QtWidgets import QApplication; import requests, jwt, dotenv"
if errorlevel 1 (
    echo No fue posible cargar las dependencias del escritorio.
    echo Activa el entorno virtual e instala requirements.txt; consulta README.md.
    goto error
)
"%PYTHON_EXE%" %PYTHON_ARGS% -m siget_desktop.main %*
set "SIGET_EXIT_CODE=%ERRORLEVEL%"
if not "%SIGET_EXIT_CODE%"=="0" (
    echo SIGET Escritorio termino con un error. Revisa el mensaje anterior.
    pause
)
popd
exit /b %SIGET_EXIT_CODE%

:error
popd
pause
exit /b 1
