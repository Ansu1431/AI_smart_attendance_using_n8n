# 📧 Email Configuration - Where to Enter Your Data

You have **3 easy ways** to configure your email settings. Choose the method you prefer:

---

## 🎯 Method 1: Configuration File (EASIEST - Recommended)

### Step 1: Create the config file
1. In your project folder, find `email_config.py.example`
2. **Copy it** and rename to `email_config.py`
3. Open `email_config.py` in any text editor

### Step 2: Enter your email details
Edit the file and replace with your actual values:

```python
# SMTP Server Configuration
MAIL_SERVER = 'smtp.gmail.com'  # ← Enter your SMTP server here
MAIL_PORT = 587                  # ← Enter port here (usually 587)
MAIL_USE_TLS = True              # ← Keep True for port 587
MAIL_USE_SSL = False             # ← Keep False for port 587

# Your email credentials
MAIL_USERNAME = 'your-email@gmail.com'      # ← Your email address
MAIL_PASSWORD = 'your-app-password'         # ← Your email password/App Password
MAIL_DEFAULT_SENDER = 'your-email@gmail.com'  # ← Usually same as MAIL_USERNAME

# Admin details
ADMIN_EMAIL = 'admin@example.com'  # ← Admin email (for password reset)
ADMIN_NAME = 'Admin'                # ← Admin display name
```

### Step 3: Save and run
- Save the file
- Run: `python app.py`
- Done! ✅

---

## ⚡ Method 2: Windows Batch Script (Quick Setup)

1. Double-click `setup_email.bat` in your project folder
2. Enter your email details when prompted
3. Close and reopen your terminal
4. Run: `python app.py`

---

## 🔧 Method 3: PowerShell Environment Variables

### For Current Session Only:
Open PowerShell in your project folder and run:

```powershell
$env:MAIL_SERVER = "smtp.gmail.com"
$env:MAIL_PORT = "587"
$env:MAIL_USERNAME = "your-email@gmail.com"
$env:MAIL_PASSWORD = "your-app-password"
$env:ADMIN_EMAIL = "admin@example.com"
$env:ADMIN_NAME = "Admin"
python app.py
```

### For Permanent Setup:
Open PowerShell as Administrator:

```powershell
setx MAIL_SERVER "smtp.gmail.com"
setx MAIL_PORT "587"
setx MAIL_USERNAME "your-email@gmail.com"
setx MAIL_PASSWORD "your-app-password"
setx ADMIN_EMAIL "admin@example.com"
setx ADMIN_NAME "Admin"
```

**Then close and reopen your terminal** before running the app.

---

## 📋 Common Email Provider Settings

### Gmail
- **MAIL_SERVER**: `smtp.gmail.com`
- **MAIL_PORT**: `587`
- **MAIL_USE_TLS**: `True`
- **MAIL_USE_SSL**: `False`
- **MAIL_USERNAME**: Your Gmail address
- **MAIL_PASSWORD**: App Password (see below)

**⚠️ Gmail requires App Password:**
1. Go to: https://myaccount.google.com/apppasswords
2. Enable 2-Factor Authentication first
3. Generate an App Password
4. Use that App Password (not your regular password)

### Outlook
- **MAIL_SERVER**: `smtp-mail.outlook.com`
- **MAIL_PORT**: `587`
- **MAIL_USE_TLS**: `True`

### Yahoo
- **MAIL_SERVER**: `smtp.mail.yahoo.com`
- **MAIL_PORT**: `587`
- **MAIL_USE_TLS**: `True`

---

## ✅ Quick Checklist

- [ ] Choose a configuration method (Method 1 recommended)
- [ ] Enter your SMTP server address
- [ ] Enter your email and password
- [ ] Set ADMIN_EMAIL to your admin email
- [ ] Save your configuration
- [ ] Run the server and test forgot password

---

## 🆘 Need Help?

Check `EMAIL_SETUP.md` for detailed troubleshooting guide.
