@echo off
setlocal
set "SCRIPT_DIR=%~dp0"

REM ============================================================
REM  organize_photos.bat
REM
REM  Renames undated photos by their EXIF capture date, in place.
REM  Recurses into subfolders (e.g. pan* folders) to find photos.
REM  Files are NOT moved; each stays in the folder it is found in.
REM
REM  HOW TO RUN
REM    Double-click this file             Process the folder it lives in
REM    organize_photos.bat                Process the current folder
REM    organize_photos.bat "C:\MyPhotos"  Process a specific folder
REM    organize_photos.bat "C:\x\IMG.jpg" Rename just that one file
REM    Drag a FOLDER onto this file       Process that folder (recursively)
REM    Drag a FILE onto this file         Rename just that file
REM    organize_photos.bat -h             Show this help
REM
REM  OPTIONS
REM    <folder>          Target directory (default: current directory)
REM    <file>            A single photo to rename (EXIF date)
REM    -h, -?, /?, --help   Show help
REM
REM  WHAT IT DOES
REM    - Recurses into subfolders (e.g. pan* folders) to find photos
REM    - Name has a date (2024.05.17_... or PXL_20240517...) -> left as-is
REM    - Name has NO date (raw ARW/CR2/NEF) -> renamed IN PLACE to
REM      YYYY.MM.DDHH.MM.SS<name> from the EXIF capture date
REM    - Files are NOT moved; they stay in the folder they are found in
REM    - Also renames .caption / .xmp sidecar files to match
REM    - Skips a file if the new name already exists (no overwrite)
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
echo   (no args)            Process the current folder (recursively)
echo   folder               Process the given folder (recursively)
echo   file                 Rename just that one file (EXIF date)
echo   -h, -?, /?, --help  Show this help
echo.
echo Undated photos are renamed in place from their EXIF capture date
echo (YYYY.MM.DDHH.MM.SS prefix). Files are NOT moved; they stay in the
echo folder they are found in. Dated names are left as-is.
echo Needs exiftool for the undated case.
goto end

REM --- Run ---
:run
if defined TARGET (
    if exist "%TARGET%\" (
        echo Renaming photos in: %TARGET%
        powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%organize_photos.ps1" -Target "%TARGET%"
    ) else if exist "%TARGET%" (
        echo Renaming file: %TARGET%
        powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%organize_photos.ps1" -Target "%TARGET%"
    ) else (
        echo ERROR: Not found: %TARGET%
        goto end
    )
) else (
    echo Renaming photos in: %CD%
    powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%organize_photos.ps1"
)

:end
endlocal
pause
