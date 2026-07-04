@echo off
REM ============================================================
REM  Build vMixController.exe  (run this on the Windows vMix PC)
REM  Requirements: Python 3.10+ installed with "Add to PATH"
REM  Files needed in this folder:
REM    - vMixController.py
REM    - index.html        (the web app; bundled into the exe,
REM                         auto-copied to C:\vMixData on first run)
REM ============================================================

echo [1/3] Installing dependencies...
python -m pip install --upgrade pip >nul
python -m pip install pyinstaller tkinterdnd2 pystray pillow
if errorlevel 1 goto :err

echo [2/3] Building vMixController.exe ...
python -m PyInstaller --noconfirm --onefile --windowed ^
  --name vMixController ^
  --collect-all tkinterdnd2 ^
  --add-data "index.html;." ^
  vMixController.py
if errorlevel 1 goto :err

echo [3/3] Done!
echo.
echo   EXE: %CD%\dist\vMixController.exe
echo   First run creates C:\vMixData  (config.json, logos\, index.html)
echo   Tip: put a shortcut to the exe in shell:startup to auto-start.
echo.
pause
exit /b 0

:err
echo.
echo BUILD FAILED - check the error above.
pause
exit /b 1
