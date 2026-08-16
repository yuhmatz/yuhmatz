@echo off
chcp 65001 >nul
rem הפעלה בלחיצה כפולה ב-Windows.

cd /d "%~dp0"

where node >nul 2>nul
if errorlevel 1 (
  echo.
  echo   Node.js is not installed / לא נמצא Node.js על המחשב
  echo   Download the LTS version from https://nodejs.org and try again
  echo.
  pause
  exit /b 1
)

start "" "http://localhost:4173"

echo.
echo   מפעיל את מערכת גביית שכר הדירה...
echo   לעצירה: Ctrl+C  ^|  לסגירה: לסגור את החלון הזה
echo.
node server.js
pause
