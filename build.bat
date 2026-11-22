@echo off
REM Rama 7 - construye dist\FORJA.exe (PyInstaller, un solo archivo, sin consola, con icono).
REM   build.bat            construye
REM   build.bat instalar   construye y, además, instala (copia a %LOCALAPPDATA%\Programs\FORJA + accesos directos)
cd /d %~dp0
if not exist .venv\Scripts\python.exe (
  python -m venv .venv || goto :error
  .venv\Scripts\python -m pip install -r requirements.txt || goto :error
)
.venv\Scripts\python -m pip install -q -r requirements-build.txt || goto :error
.venv\Scripts\python -m PyInstaller --noconfirm --clean forja.spec || goto :error
echo.
echo Listo: dist\FORJA.exe
if /i "%1"=="instalar" dist\FORJA.exe --instalar
goto :eof
:error
echo No se pudo construir FORJA.exe.
exit /b 1
