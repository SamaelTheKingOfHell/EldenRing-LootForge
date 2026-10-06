@echo off
set GAME_DIR=D:\SteamLibrary\steamapps\common\ELDEN RING\Game
set OUTPUT_DIR=%~dp0backups\msg

echo Testing MSG extraction from Data0.bdt...
echo.
echo Game Directory: %GAME_DIR%
echo Output Directory: %OUTPUT_DIR%
echo.

tools\RegTool\bin\Release\net9.0\RegTool.exe extract-msg --game-dir "%GAME_DIR%" --output "%OUTPUT_DIR%"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo SUCCESS! Check backups\msg\engUS\item.msgbnd.dcx
    dir "%OUTPUT_DIR%\engUS\item.msgbnd.dcx"
) else (
    echo.
    echo FAILED with error code %ERRORLEVEL%
)

pause
