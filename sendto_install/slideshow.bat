@echo off
setlocal
set "BIN_DIR=%USERPROFILE%\bin"
set "SCRIPT_DIR=%~dp0"
REM Find slideshow.exe: %USERPROFILE%\bin\slideshow, then repo dist (next to or above this .bat)
set "EXE=%BIN_DIR%\slideshow\slideshow.exe"
if not exist "%EXE%" set "EXE=%SCRIPT_DIR%slideshow\dist\slideshow.exe"
if not exist "%EXE%" set "EXE=%SCRIPT_DIR%..\slideshow\dist\slideshow.exe"

REM ============================================================
REM  slideshow.bat
REM
REM  Starts the sequential photo slideshow on a folder.
REM
REM  HOW TO RUN
REM    Double-click this file           Folder picker opens
REM    slideshow.bat                    Folder picker opens
REM    slideshow.bat "C:\MyPhotos"      Slideshow that folder
REM    slideshow.bat "C:\MyPhotos" 10   ... with a 10s interval
REM    Drag a FOLDER onto this file     Slideshow that folder
REM    Drag a FILE onto this file       Slideshow the file's folder
REM    slideshow.bat -h                 Show this help
REM
REM  OPTIONS
REM    <folder>          Photo directory (default: native folder picker)
REM    <seconds>         Slide interval in seconds (default: 5)
REM    -h, -?, /?, --help   Show help
REM
REM  INSTALL
REM    Run install.exe to place this file in %USERPROFILE%\bin and
REM    shell:sendto, and the app under %USERPROFILE%\bin\slideshow.
REM    Then: right-click a folder > Send to > slideshow.bat
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
echo Usage: slideshow.bat [folder] [seconds] [options]
echo.
echo   (no args)            Open the native folder picker
echo   folder               Slideshow the given folder
echo   folder seconds       Slideshow with a slide interval in seconds
echo   -h, -?, /?, --help  Show this help
echo.
echo Sequential photo slideshow (%USERPROFILE%\bin\slideshow\slideshow.exe).
echo Drop a folder (or a file, to use its folder) onto this .bat, or
echo right-click a folder and Send to slideshow.bat.
goto end

REM --- Run ---
:run
if not exist "%EXE%" (
    echo ERROR: slideshow.exe not found.
    echo   Looked in: %BIN_DIR%\slideshow
    echo              %SCRIPT_DIR%slideshow\dist
    echo              %SCRIPT_DIR%..\slideshow\dist
    echo Run sendto_install\install.exe first, or build the app.
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
    echo ERROR: Not found: "%TARGET%"
    goto end
)
if "%FOLDER:~-1%"=="\" set "FOLDER=%FOLDER:~0,-1%"

if defined INTERVAL (
    echo Slideshow: "%FOLDER%"  interval: %INTERVAL%s
    start "" "%EXE%" "%FOLDER%" "%INTERVAL%"
) else (
    echo Slideshow: "%FOLDER%"
    start "" "%EXE%" "%FOLDER%"
)

:end
endlocal
