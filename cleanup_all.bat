@echo off
REM cleanup_all.bat - run cleanup_gallery.py over every www_* gallery dir.
REM
REM Usage:
REM   cleanup_all.bat --dry-run                 preview all sites
REM   cleanup_all.bat                           clean all sites
REM   cleanup_all.bat --base D:\www             scan another base dir
REM   cleanup_all.bat --only www_misc           just one
REM   cleanup_all.bat -- --all                  forward --all to cleanup_gallery.py
REM
REM Default base: %CLEANUP_BASE% if set, else /var/www (on Windows override
REM with --base or set CLEANUP_BASE).
setlocal
set "SCRIPT_DIR=%~dp0"

where py >nul 2>&1
if %ERRORLEVEL%==0 (
    py -3 "%SCRIPT_DIR%cleanup_all.py" %*
) else (
    python "%SCRIPT_DIR%cleanup_all.py" %*
)
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
    echo.
    echo cleanup_all finished with errors ^(exit %RC%^)
)
endlocal & exit /b %RC%
