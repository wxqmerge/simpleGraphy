@echo off
setlocal
set "BIN_DIR=%USERPROFILE%\bin"
set "SCRIPT_DIR=%~dp0"

REM ============================================================
REM  move_jpg.bat
REM
REM  Moves all .jpg / .jpeg files in a folder into a subdirectory
REM  with the same name as that folder.
REM
REM  HOW TO RUN
REM    Double-click this file              Process the folder it lives in
REM    move_jpg.bat                        Process the current folder
REM    move_jpg.bat "C:\MyPhotos"          Process a specific folder
REM    Drag a FOLDER onto this file        Process that folder
REM    move_jpg.bat -h                     Show this help
REM
REM  OPTIONS
REM    <folder>          Target directory (default: current directory)
REM    -h, -?, /?, --help   Show help
REM
REM  WHAT IT DOES
REM    - Creates a subfolder named after the target folder
REM      (e.g. C:\Photos\MyTrip -> C:\Photos\MyTrip\MyTrip\)
REM    - Moves all .jpg / .jpeg files into that subfolder
REM    - Skips files that already exist in the target (no overwrite)
REM ============================================================

REM --- Parse arguments ---
set "TARGET="
:parse
if "%~1"=="" goto run
if /I "%~1"=="-h" goto help
if /I "%~1"=="-?" goto help
if /I "%~1"=="/?" goto help
if /I "%~1"=="--help" goto help
if not defined TARGET set "TARGET=%~1"
shift
goto parse

REM --- Show help ---
:help
echo Usage: move_jpg.bat [folder] [options]
echo.
echo   (no args)            Process the current folder
echo   folder               Process the given folder
echo   -h, -?, /?, --help  Show this help
echo.
echo Moves all .jpg / .jpeg files into a subfolder named after
echo the target folder.
goto end

REM --- Run ---
:run
set "DIR="
if defined TARGET goto have_target
set "DIR=%CD%"
goto do_move

:have_target
if exist "%TARGET%\" set "DIR=%TARGET%"
if not defined DIR (
    echo ERROR: Not a folder: %TARGET%
    goto end
)

:do_move

REM Get the folder name (last path component)
for %%I in ("%DIR%") do set "FOLDER_NAME=%%~nxI"

set "DEST=%DIR%\%FOLDER_NAME%"

echo Moving JPGs in: "%DIR%"
echo Destination:   "%DEST%"

if not exist "%DEST%\" mkdir "%DEST%"

set "MOVED=0"
set "SKIPPED=0"

for %%F in ("%DIR%\*.jpg" "%DIR%\*.jpeg" "%DIR%\*.JPG" "%DIR%\*.JPEG") do (
    if exist "%%F" call :try_move "%%F"
)

echo.
echo Done. Moved: %MOVED%  Skipped: %SKIPPED%
goto end

:try_move
set "NAME=%~nx1"
if exist "%DEST%\%NAME%" (
    echo SKIP exists: "%NAME%"
    set /a SKIPPED+=1
) else (
    move "%~1" "%DEST%\" >nul
    echo Moved: "%NAME%"
    set /a MOVED+=1
)
goto :eof

:end
endlocal
pause
