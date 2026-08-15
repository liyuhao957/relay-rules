@echo off
call "%~dp0relay.cmd" remove %*
exit /b %errorlevel%
