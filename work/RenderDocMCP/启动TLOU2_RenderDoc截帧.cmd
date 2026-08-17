@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "RDOC=C:\Work\AI\Iris\work\RenderDocMCP\tools\renderdoc_src_2fc0bc04\x64\Development\renderdoccmd.exe"
set "GAMEDIR=D:\Work\Company\Game\The Last Of Us Part II (2020-2025)\The Last of Us II Rematered"
set "GAME=!GAMEDIR!\tlou-ii.exe"
set "CAPTURE_ROOT=C:\Work\AI\Iris\work\RenderDocMCP\captures\tlou2_manual"

if not exist "!RDOC!" goto missing_renderdoc
if not exist "!GAME!" goto missing_game

powershell.exe -NoProfile -Command "if (Get-Process -Name 'tlou-ii' -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if not errorlevel 1 goto game_running

for /f %%I in ('powershell.exe -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
if not defined STAMP set "STAMP=run_!RANDOM!"

set "OUTDIR=!CAPTURE_ROOT!\!STAMP!"
if not exist "!OUTDIR!" mkdir "!OUTDIR!"
if not exist "!OUTDIR!" goto create_dir_failed

echo Starting TLOU2 with the Streamline-aware RenderDoc build...
echo Captures will be saved to:
echo !OUTDIR!
echo.
echo After the game starts:
echo   1. Click Start Game in the launcher window.
echo   2. Wait for the RenderDoc overlay in the top-left corner.
echo   3. Press F12 once and wait for the capture to finish writing.
echo.

"!RDOC!" capture --working-dir "!GAMEDIR!" --capture-file "!OUTDIR!\tlou2" "!GAME!"
set "RESULT=!ERRORLEVEL!"
powershell.exe -NoProfile -Command "Start-Sleep -Seconds 3"
powershell.exe -NoProfile -Command "if (Get-Process -Name 'tlou-ii' -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if errorlevel 1 goto launch_failed

echo.
echo RenderDoc injection was started successfully.
echo You can close this window.
powershell.exe -NoProfile -Command "Start-Sleep -Seconds 3"
exit /b 0

:missing_renderdoc
echo [ERROR] Custom RenderDoc was not found:
echo !RDOC!
goto failed

:missing_game
echo [ERROR] The game executable was not found:
echo !GAME!
goto failed

:game_running
echo [ERROR] tlou-ii.exe is already running. Exit the game first.
goto failed

:create_dir_failed
echo [ERROR] Could not create capture directory:
echo !OUTDIR!
goto failed

:launch_failed
echo [ERROR] RenderDoc failed to launch the game. Exit code: !RESULT!
goto failed

:failed
echo.
pause
exit /b 1
