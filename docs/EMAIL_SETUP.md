# Email Configuration Guide

You can configure email settings using **two methods**. Choose the one that's easiest for you:

## Method 1: Using Configuration File (Easiest) ⭐ Recommended

1. **Copy the example file:**
   ```
   Copy `email_config.py.example` to `email_config.py`
   ```

2. **Edit `email_config.py` and enter your email details:**
   ```python
   # SMTP Server Configuration
   MAIL_SERVER = 'smtp.gmail.com'  # For Gmail
   MAIL_PORT = 587
   MAIL_USE_TLS = True
   MAIL_USE_SSL = False

   # Your email credentials
   MAIL_USERNAME = 'your-email@gmail.com'
   MAIL_PASSWORD = 'your-app-password'
   MAIL_DEFAULT_SENDER = 'your-email@gmail.com'

   # Admin details
   ADMIN_EMAIL = 'admin@example.com'
   ADMIN_NAME = 'Admin'
   ```

3. **Save the file** - That's it! The app will automatically load these settings.

---

## Method 2: Using Environment Variables (Windows PowerShell)

### Option A: Set for Current Session (Temporary)
Open PowerShell in your project folder and run:

```powershell
$env:MAIL_SERVER = "smtp.gmail.com"
$env:MAIL_PORT = "587"
$env:MAIL_USE_TLS = "true"
$env:MAIL_USE_SSL = "false"
$env:MAIL_USERNAME = "your-email@gmail.com"
$env:MAIL_PASSWORD = "your-app-password"
$env:MAIL_DEFAULT_SENDER = "your-email@gmail.com"
$env:ADMIN_EMAIL = "admin@example.com"
$env:ADMIN_NAME = "Admin"
python app.py
```

### Option B: Set Permanently (System-wide)
Open PowerShell as Administrator and run:

```powershell
setx MAIL_SERVER "smtp.gmail.com"
setx MAIL_PORT "587"
setx MAIL_USE_TLS "true"
setx MAIL_USE_SSL "false"
setx MAIL_USERNAME "your-email@gmail.com"
setx MAIL_PASSWORD "your-app-password"
setx MAIL_DEFAULT_SENDER "your-email@gmail.com"
setx ADMIN_EMAIL "admin@example.com"
setx ADMIN_NAME "Admin"
```

**Note:** After using `setx`, you need to close and reopen your terminal/PowerShell window.

---

## Email Provider Settings

### Gmail
```
MAIL_SERVER = 'smtp.gmail.com'
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USE_SSL = False
```

**Important for Gmail:**
1. Enable 2-Factor Authentication on your Google account
2. Generate an App Password: https://myaccount.google.com/apppasswords
3. Use the App Password (not your regular password) in `MAIL_PASSWORD`

### Outlook/Hotmail
```
MAIL_SERVER = 'smtp-mail.outlook.com'
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USE_SSL = False
```

### Yahoo
```
MAIL_SERVER = 'smtp.mail.yahoo.com'
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USE_SSL = False
```

### Custom SMTP Server
Contact your email provider for SMTP settings and adjust accordingly.

---

## Quick Setup Steps

1. **Choose Method 1 (Configuration File)** - It's the easiest!
2. Copy `email_config.py.example` to `email_config.py`
3. Fill in your email details in `email_config.py`
4. Run the server: `python app.py`
5. Test the forgot password feature

---

## Security Notes

- ⚠️ Never commit `email_config.py` to git (it's already in .gitignore)
- ⚠️ Never share your email password or App Password
- ⚠️ For production, use environment variables or a secure secrets manager

---

## Troubleshooting

**Email not sending?**
- Check your email credentials are correct
- For Gmail, make sure you're using an App Password, not your regular password
- Check firewall/antivirus isn't blocking SMTP connections
- Verify SMTP server and port are correct for your email provider

**"Failed to send email" error?**
- Check the terminal/console for detailed error messages
- Verify all email settings are correct
- Test your email credentials by logging into your email account
