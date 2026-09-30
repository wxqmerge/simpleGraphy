@echo off
setlocal
set "SCRIPT_DIR=%~dp0"

REM ============================================================
REM  organize_photos.bat
REM
REM  Sorts photos in a folder into YYMMDD subfolders.
REM  Files whose name has no date (e.g. raw ARW) are renamed using
REM  their EXIF capture date, then sorted.
REM
REM  HOW TO RUN
REM    Double-click this file             Organize the folder it lives in
REM    organize_photos.bat                Organize the current folder
REM    organize_photos.bat "C:\MyPhotos"  Organize a specific folder
REM    organize_photos.bat "C:\x\IMG.jpg" Rename just that one file
REM    Drag a FOLDER onto this file       Organize that folder
REM    Drag a FILE onto this file         Rename just that file
REM    organize_photos.bat -h             Show this help
REM
REM  OPTIONS
REM    <folder>          Target directory (default: current directory)
REM    <file>            A single photo to rename (EXIF date)
REM    -h, -?, /?, --help   Show help
REM
REM  WHAT IT DOES
REM    - Name has a date (2024.05.17_... or PXL_20240517...) -> moved as-is
REM    - Name has NO date (raw ARW/CR2/NEF) -> renamed to
REM      YYYY.MM.DDHH.MM.SS<name> from the EXIF capture date, then moved
REM    - Moves each photo into a YYMMDD folder (e.g. 250517)
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
echo Usage: organize_photos.bat [folder-or-file] [options]
echo.
echo   (no args)            Organize the current folder
echo   folder               Organize the given folder
echo   file                 Rename just that one file (EXIF date)
echo   -h, -?, /?, --help  Show this help
echo.
echo Photos are sorted into YYMMDD subfolders.
echo   - Dated names (2024.05.17_... / PXL_20240517...) are moved as-is.
echo   - Undated names (raw ARW/CR2/NEF) are renamed from their EXIF
echo     capture date (YYYY.MM.DDHH.MM.SS prefix), then moved.
echo   - Needs exiftool for the undated case.
goto end

REM --- Run ---
:run
if defined TARGET (
    if exist "%TARGET%\" (
        echo Organizing folder: %TARGET%
        powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%organize_photos.ps1" -Target "%TARGET%"
    ) else if exist "%TARGET%" (
        echo Organizing file: %TARGET%
        powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%organize_photos.ps1" -Target "%TARGET%"
    ) else (
        echo ERROR: Not found: %TARGET%
        goto end
    )
) else (
    echo Organizing: %CD%
    powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%organize_photos.ps1"
)

:end
endlocal
pause
