@echo off
echo ========================================
echo Email Configuration Setup
echo ========================================
echo.
echo This script will help you set up email configuration.
echo.

set /p MAIL_SERVER="Enter SMTP Server (e.g., smtp.gmail.com): "
set /p MAIL_PORT="Enter SMTP Port (e.g., 587): "
set /p MAIL_USERNAME="Enter Your Email: "
set /p MAIL_PASSWORD="Enter Email Password/App Password: "
set /p ADMIN_EMAIL="Enter Admin Email: "
set /p ADMIN_NAME="Enter Admin Name: "

echo.
echo Setting environment variables...

setx MAIL_SERVER "%MAIL_SERVER%"
setx MAIL_PORT "%MAIL_PORT%"
setx MAIL_USE_TLS "true"
setx MAIL_USE_SSL "false"
setx MAIL_USERNAME "%MAIL_USERNAME%"
setx MAIL_PASSWORD "%MAIL_PASSWORD%"
setx MAIL_DEFAULT_SENDER "%MAIL_USERNAME%"
setx ADMIN_EMAIL "%ADMIN_EMAIL%"
setx ADMIN_NAME "%ADMIN_NAME%"

echo.
echo ========================================
echo Configuration saved!
echo ========================================
echo.
echo NOTE: Please close and reopen your terminal/PowerShell
echo       for the changes to take effect.
echo.
pause
