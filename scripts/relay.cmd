@echo off
setlocal
set "PYTHONUTF8=1"

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
if not errorlevel 1 goto use_python
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
if not errorlevel 1 goto use_launcher
echo error: Python 3.9 or newer was not found via python or py -3. 1>&2
exit /b 127

:use_python
python "%~dp0relay.py" %*
exit /b %errorlevel%

:use_launcher
py -3 "%~dp0relay.py" %*
exit /b %errorlevel%
