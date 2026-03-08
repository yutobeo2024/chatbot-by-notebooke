@echo off
set "CHROME_PATH=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if exist "%CHROME_PATH%" (
    echo [OK] Chrome found at: %CHROME_PATH%
    set "PATH=%PATH%;C:\Program Files (x86)\Google\Chrome\Application"
    notebooklm-mcp-auth
) else (
    echo [ERROR] Chrome not found at %CHROME_PATH%
    echo Please run: notebooklm-mcp-auth --file
)
pause
