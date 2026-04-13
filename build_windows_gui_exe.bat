@echo off
setlocal
cd /d "%~dp0"

echo ==============================================
echo Building PhotoVideoSorter GUI EXE

echo ==============================================
py -m pip install --upgrade pip
py -m pip install -r requirements_gui_build.txt
py -m PyInstaller --noconfirm --onefile --windowed --name PhotoVideoSorterGUI photo_sorter_gui.py

echo.
echo Build complete.
echo EXE location:
echo %~dp0dist\PhotoVideoSorterGUI.exe
pause
