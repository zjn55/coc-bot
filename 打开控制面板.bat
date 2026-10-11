@echo off
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 goto nopython

python -c "import cv2, numpy" >nul 2>nul
if errorlevel 1 pip install opencv-python numpy pywin32

python "COC¾è±øGUI.py"
pause
exit

:nopython
echo [ERROR] Python not found!
echo Please install Python 3.10+ and check Add Python to PATH
echo Download: https://www.python.org/downloads/
pause
