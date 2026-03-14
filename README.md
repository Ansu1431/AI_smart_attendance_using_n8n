# Face Recognition Attendance System

A modern Flask-based web application for face recognition-based attendance tracking. Features a beautiful UI with glassmorphism design, admin dashboard, and email-based password recovery.

## 📁 Project Structure

```
attendance/
├── app.py              # Main Flask application
├── config/             # Configuration files (email_config.py)
├── data/               # Attendance records (CSV/Excel)
├── docs/               # Documentation
├── scripts/            # Utility scripts
├── static/             # CSS, JS, and student images
└── templates/          # HTML templates
```

For detailed structure, see [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md)

## ✨ Features

- **Face Recognition Attendance** - Webcam-based face recognition for attendance
- **Modern UI** - Beautiful glassmorphism design with animations
- **Admin Dashboard** - Comprehensive admin panel with statistics
- **Password Recovery** - Email-based forgot password functionality
- **Certified Badge** - Professional certification indicator
- **Responsive Design** - Works on desktop and mobile devices

How it works

- Student page captures a snapshot as a base64 JPEG and POSTs it to `/api/verify`.
- The server compares the captured face with images placed in the `images/` directory.
- Admin can login (password from `ADMIN_PASSWORD` env var or `.admin_password` file, default `admin123`) and add a student (upload name + image) or remove them.
- Forgot password functionality sends reset links via email.

Run locally (Windows PowerShell):

```powershell
python -m pip install -r requirements.txt
setx ADMIN_PASSWORD "yourpassword"  # optional
setx ADMIN_EMAIL "admin@example.com"  # required for password reset
python app.py
```

Then open http://127.0.0.1:5000 in your browser.

## Email Configuration (For Password Reset)

To enable password reset functionality, configure email settings via environment variables:

```powershell
# Gmail example
setx MAIL_SERVER "smtp.gmail.com"
setx MAIL_PORT "587"
setx MAIL_USE_TLS "true"
setx MAIL_USERNAME "your-email@gmail.com"
setx MAIL_PASSWORD "your-app-password"  # Use App Password for Gmail
setx MAIL_DEFAULT_SENDER "your-email@gmail.com"
setx ADMIN_EMAIL "admin@example.com"
setx ADMIN_NAME "Admin Name"
```

**For Gmail users:**
1. Enable 2-Factor Authentication
2. Generate an App Password: https://myaccount.google.com/apppasswords
3. Use the App Password in `MAIL_PASSWORD`

**Other email providers:**
- Outlook: `smtp-mail.outlook.com`, port 587
- Yahoo: `smtp.mail.yahoo.com`, port 587
- Custom SMTP: Configure according to your provider

Notes & next steps

- This is a minimal implementation to get you started. For production use: secure the admin endpoint, persist attendance records, and add robust error handling.
- The system uses one reference image per student stored in `images/`.
- Password reset tokens expire after 1 hour.
- Admin password is stored in `.admin_password` file (auto-generated after first reset) or environment variable.