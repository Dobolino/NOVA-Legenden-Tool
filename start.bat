@echo off
rem Start NOVA-Legenden from the source code (for development and testing).
rem First run: creates a Python environment and builds the user interface.
cd /d "%~dp0"
if not exist .venv (
  echo Richte Python-Umgebung ein ...
  python -m venv .venv || goto :error
  call .venv\Scripts\activate.bat
  pip install -r backend\requirements.txt -r packaging\requirements-windows.txt || goto :error
) else (
  call .venv\Scripts\activate.bat
)
if not exist ui\dist\index.html (
  echo Baue Oberflaeche ...
  pushd ui
  call npm install || goto :error
  call npm run build || goto :error
  popd
)
set PYTHONPATH=%~dp0backend
python -m nova_legend %*
goto :eof
:error
echo Fehler beim Einrichten. Details stehen oben.
pause
