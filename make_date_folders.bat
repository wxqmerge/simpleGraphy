@echo off
setlocal
set "SCRIPT_DIR=%~dp0"

REM ============================================================
REM  make_date_folders.bat
REM
REM  Moves photos into per-date (YYMMDD) folders, at the top level
REM  of a folder. Subfolders are NOT scanned.
REM  Undated files (raw ARW/CR2/NEF) are renamed by their EXIF
REM  capture date first, then moved.
REM
REM  HOW TO RUN
REM    Double-click this file              Organize the folder it lives in
REM    make_date_folders.bat               Organize the current folder
REM    make_date_folders.bat "C:\MyPhotos" Organize a specific folder
REM    make_date_folders.bat "C:\x\IMG.jpg" Move just that one file
REM    Drag a FOLDER onto this file        Organize that folder
REM    Drag a FILE onto this file          Move just that file
REM    make_date_folders.bat -h            Show this help
REM
REM  OPTIONS
REM    <folder>          Target directory (default: current directory)
REM    <file>            A single photo to move
REM    -h, -?, /?, --help   Show help
REM
REM  WHAT IT DOES
REM    - Name has a date (2024.05.17_... or PXL_20240517...) -> moved as-is
REM    - Name has NO date (raw ARW/CR2/NEF) -> renamed to
REM      YYYY.MM.DDHH.MM.SS<name> from the EXIF capture date, then moved
REM    - Moves each photo into a YYMMDD folder (e.g. 250517)
REM    - Only the top level is scanned; subfolders are ignored
REM    - Also moves .caption / .xmp sidecar files along (renamed to match)
REM    - Skips a file if the target already exists (no overwrite)
REM    - Needs exiftool for the no-date case (C:\Users\wxqme\bin\exiftool.exe)
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
echo Usage: make_date_folders.bat [folder-or-file] [options]
echo.
echo   (no args)            Organize the current folder (top level only)
echo   folder               Organize the given folder (top level only)
echo   file                 Move just that one file
echo   -h, -?, /?, --help  Show this help
echo.
echo Photos are moved into YYMMDD subfolders (top level only; subfolders
echo are ignored). Dated names are moved as-is; undated names are renamed
echo from their EXIF capture date (YYYY.MM.DDHH.MM.SS prefix), then moved.
echo Needs exiftool for the undated case.
goto end

REM --- Run ---
:run
if defined TARGET (
    if exist "%TARGET%\" (
        echo Organizing folder: %TARGET%
        powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%make_date_folders.ps1" -Target "%TARGET%"
    ) else if exist "%TARGET%" (
        echo Organizing file: %TARGET%
        powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%make_date_folders.ps1" -Target "%TARGET%"
    ) else (
        echo ERROR: Not found: %TARGET%
        goto end
    )
) else (
    echo Organizing: %CD%
    powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%make_date_folders.ps1"
)

:end
endlocal
pause
