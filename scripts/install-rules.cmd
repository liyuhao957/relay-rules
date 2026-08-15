@echo off
call "%~dp0relay.cmd" install %*
exit /b %errorlevel%
