@echo off
setlocal
set "BIN_DIR=%USERPROFILE%\bin"
set "SCRIPT_DIR=%~dp0"
REM Find the .ps1: prefer %USERPROFILE%\bin, fall back to next to this .bat
set "PS1=%BIN_DIR%\make_pan.ps1"
if not exist "%PS1%" set "PS1=%SCRIPT_DIR%make_pan.ps1"

REM ============================================================
REM  make_pan.bat
REM
REM  Moves the selected files into one pan_xxxxx folder.
REM
REM  HOW TO RUN
REM    Select files in Explorer > right-click > Send to >
REM    make_pan.bat
REM    make_pan.bat "C:\a\DSC02799.ARW" "C:\a\DSC02800.ARW"
REM    make_pan.bat -h                  Show this help
REM
REM  WHAT IT DOES
REM    - Creates a folder named pan_xxxxx next to the FIRST file
REM    - xxxxx = digits after DSC in the first file's name
REM      (DSC02799 -> pan_02799)
REM    - No DSC in the first name -> unique random 5-digit number
REM      (checked against existing pan_* folders, never reused)
REM    - Moves all given files into that folder
REM    - Also moves .caption / .xmp sidecar files along
REM    - Never overwrites: same name in target -> skipped
REM    - A file already inside the target folder -> skipped
REM ============================================================

REM --- Show help ---
if /I "%~1"=="-h" goto help
if /I "%~1"=="-?" goto help
if /I "%~1"=="/?" goto help
if /I "%~1"=="--help" goto help

REM --- No files given ---
if "%~1"=="" goto nopath

powershell -ExecutionPolicy Bypass -File "%PS1%" %*
goto end

:help
echo Usage: make_pan.bat [file1] [file2] ...
echo.
echo   Select files in Explorer, then right-click and Send to make_pan.bat
echo.
echo   Files are moved into one pan_xxxxx folder, created next to
echo   the FIRST file:
echo     first name has DSC digits  ...  pan_digits  (e.g. pan_02799)
echo     no DSC in first name       ...  unique random pan_#####
echo.
echo   .caption / .xmp sidecars move along. Nothing is overwritten.
goto end

:nopath
echo ERROR: No files selected.
echo.
echo   Select the files in Explorer, right-click, Send to, make_pan.bat
echo   (or run: make_pan.bat "C:\path\DSC02799.ARW" ...)
goto end

:end
endlocal
pause
