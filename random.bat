@echo off
setlocal
set "BIN_DIR=%USERPROFILE%\bin"
set "SCRIPT_DIR=%~dp0"
REM Find random.exe: prefer %USERPROFILE%\bin\random, fall back to repo dist next to this .bat
set "EXE=%BIN_DIR%\random\random.exe"
if not exist "%EXE%" set "EXE=%SCRIPT_DIR%random\dist\random.exe"

REM ============================================================
REM  random.bat
REM
REM  Starts the randomized photo slideshow on a folder.
REM
REM  HOW TO RUN
REM    Double-click this file           Folder picker opens
REM    random.bat                       Folder picker opens
REM    random.bat "C:\MyPhotos"         Slideshow that folder
REM    random.bat "C:\MyPhotos" 10      ... with a 10s interval
REM    Drag a FOLDER onto this file     Slideshow that folder
REM    Drag a FILE onto this file       Slideshow the file's folder
REM    random.bat -h                    Show this help
REM
REM  OPTIONS
REM    <folder>          Photo directory (default: native folder picker)
REM    <seconds>         Slide interval in seconds (default: 5)
REM    -h, -?, /?, --help   Show help
REM
REM  INSTALL
REM    Run install.exe to place this file in %USERPROFILE%\bin and
REM    shell:sendto, and the app under %USERPROFILE%\bin\random.
REM    Then: right-click a folder > Send to > random.bat
REM ============================================================

REM --- Parse arguments ---
set "TARGET="
set "INTERVAL="
:parse
if "%~1"=="" goto run
if /I "%~1"=="-h" goto help
if /I "%~1"=="-?" goto help
if /I "%~1"=="/?" goto help
if /I "%~1"=="--help" goto help
if not defined TARGET (
    set "TARGET=%~1"
    shift
    goto parse
)
if not defined INTERVAL (
    set "INTERVAL=%~1"
    shift
    goto parse
)
shift
goto parse

REM --- Show help ---
:help
echo Usage: random.bat [folder] [seconds] [options]
echo.
echo   (no args)            Open the native folder picker
echo   folder               Slideshow the given folder
echo   folder seconds       Slideshow with a slide interval in seconds
echo   -h, -?, /?, --help  Show this help
echo.
echo Randomized photo slideshow (%USERPROFILE%\bin\random\random.exe).
echo Drop a folder (or a file, to use its folder) onto this .bat, or
echo right-click a folder and Send to random.bat.
goto end

REM --- Run ---
:run
if not exist "%EXE%" (
    echo ERROR: random.exe not found.
    echo   Looked in: %BIN_DIR%\random
    echo              %SCRIPT_DIR%random\dist
    echo Run install.exe from the simpleGraphy folder first.
    goto end
)

REM No target -> let the app show its own folder picker
if not defined TARGET (
    start "" "%EXE%"
    goto end
)

if exist "%TARGET%\" set "FOLDER=%TARGET%"
if exist "%TARGET%" if not defined FOLDER for %%I in ("%TARGET%") do set "FOLDER=%%~dpI"
if not defined FOLDER (
    echo ERROR: Not found: %TARGET%
    goto end
)
if "%FOLDER:~-1%"=="\" set "FOLDER=%FOLDER:~0,-1%"

if defined INTERVAL (
    echo Random slideshow: %FOLDER%  interval: %INTERVAL%s
    start "" "%EXE%" "%FOLDER%" "%INTERVAL%"
) else (
    echo Random slideshow: %FOLDER%
    start "" "%EXE%" "%FOLDER%"
)

:end
endlocal
