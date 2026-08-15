@echo off
call "%~dp0relay.cmd" validate-template %*
exit /b %errorlevel%
