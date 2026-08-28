@echo off
setlocal
cd /d "%~dp0"

set "FLOOR_PYTHON="
where py >nul 2>nul
if errorlevel 1 goto :try_python
py -3 -c "import sys; raise SystemExit(sys.version_info < (3, 10))" >nul 2>nul
if errorlevel 1 goto :try_python
set "FLOOR_PYTHON=py -3"
goto :python_found

:try_python
where python >nul 2>nul
if errorlevel 1 goto :version_error
python -c "import sys; raise SystemExit(sys.version_info < (3, 10))" >nul 2>nul
if errorlevel 1 goto :version_error
set "FLOOR_PYTHON=python"

:python_found

if not exist ".venv\Scripts\python.exe" (
    echo Setting up Floor Planner for the first time...
    %FLOOR_PYTHON% -m venv .venv
    if errorlevel 1 goto :setup_error
)

".venv\Scripts\python.exe" -c "import sys; raise SystemExit(sys.version_info < (3, 10))" >nul 2>nul
if errorlevel 1 goto :venv_error

".venv\Scripts\python.exe" -c "import hashlib,pathlib,sys; p=pathlib.Path('pyproject.toml'); m=pathlib.Path('.venv/.floor_planner_setup'); digest=hashlib.sha256(p.read_bytes()).hexdigest(); raise SystemExit(not (m.is_file() and m.read_text()==digest))" >nul 2>nul
if not errorlevel 1 goto :run_app

echo Installing Floor Planner. The first setup requires internet and may take a few minutes...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -e .
if errorlevel 1 goto :setup_error
".venv\Scripts\python.exe" -c "import hashlib,pathlib; p=pathlib.Path('pyproject.toml'); pathlib.Path('.venv/.floor_planner_setup').write_text(hashlib.sha256(p.read_bytes()).hexdigest())"

:run_app
".venv\Scripts\python.exe" -m floor_planner
if errorlevel 1 (
    echo.
    echo Floor Planner closed because of an error.
    pause
)
exit /b

:version_error
echo.
echo Floor Planner requires Python 3.10 or newer, but a supported Python installation was not found.
echo Install the latest Python from https://www.python.org/downloads/ and try again.
pause
exit /b 1

:venv_error
echo.
echo The existing .venv uses an old or broken Python.
echo Rename or remove the .venv folder, then run this file again.
pause
exit /b 1

:setup_error
echo.
echo Setup did not finish. Check that Python 3.10 or newer is installed and that this computer is online.
pause
exit /b 1
