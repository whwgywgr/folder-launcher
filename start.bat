@echo off
title Folder Launcher
cd /d "%~dp0"
where py >nul 2>nul && (py server.py & goto :done)
where python >nul 2>nul && (python server.py & goto :done)
echo.
echo [!] Python tidak dijumpai pada komputer ini.
echo     Sila pasang Python daripada https://www.python.org/downloads/
echo     Semasa pemasangan, tandakan "Add python.exe to PATH".
:done
echo.
pause
