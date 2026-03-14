# ⚠️ IMPORTANT: Gmail Setup for Email Sending

## The Issue
If you're seeing "Failed to send email" error, **Gmail requires an App Password**, not your regular Gmail password.

## Quick Fix - Step by Step:

### Step 1: Enable 2-Factor Authentication
1. Go to: https://myaccount.google.com/security
2. Under "Signing in to Google", click "2-Step Verification"
3. Follow the setup process

### Step 2: Generate App Password
1. Go to: https://myaccount.google.com/apppasswords
2. Select "Mail" as the app
3. Select "Other (Custom name)" and type "Attendance System"
4. Click "Generate"
5. **Copy the 16-character password** (it will look like: `abcd efgh ijkl mnop`)

### Step 3: Update email_config.py
Open `email_config.py` and update the password:

```python
MAIL_PASSWORD = 'abcdefghijklmnop'  # ← Paste your App Password here (remove spaces)
```

**Important:** Remove any spaces from the App Password when pasting.

### Step 4: Restart Server
Stop and restart your Flask server to load the new password.

## Alternative: Use a Different Email Provider

If you prefer not to use Gmail App Passwords, you can use:
- **Outlook/Hotmail**: Usually works with regular password
- **Yahoo**: Requires App Password (similar to Gmail)
- **Custom SMTP**: Depends on your provider

## Still Having Issues?

1. Check the terminal/console for detailed error messages
2. Verify your email_config.py file exists and has correct values
3. Make sure there are no extra spaces in the App Password
4. Try testing with a different email provider
