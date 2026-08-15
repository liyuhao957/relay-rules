@echo off
call "%~dp0relay.cmd" doctor %*
exit /b %errorlevel%
