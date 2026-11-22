@echo off
cd /d %~dp0
if not exist .venv\Scripts\python.exe (
  echo Creando entorno virtual...
  python -m venv .venv || goto :error
  .venv\Scripts\python -m pip install -r requirements.txt || goto :error
)
.venv\Scripts\python -m backend.main %*
goto :eof
:error
echo No se pudo preparar el entorno. Necesitas Python 3.11+ en el PATH.
pause
