@echo off
cd /d "%~dp0tools\RegTool"
echo Building RegTool...
dotnet build -c Release
if %ERRORLEVEL% EQU 0 (
    echo Build successful!
) else (
    echo Build failed with error code %ERRORLEVEL%
)
pause
