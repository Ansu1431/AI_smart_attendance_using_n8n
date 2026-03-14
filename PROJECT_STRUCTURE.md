# 📁 Project Structure

This document describes the organized folder structure of the Attendance System project.

## Directory Layout

```
attendance/
│
├── app.py                          # Main Flask application entry point
├── requirements.txt                # Python dependencies
├── README.md                       # Main project documentation
├── setup_email.bat                 # Windows batch script for email setup
├── .gitignore                      # Git ignore rules
│
├── config/                         # Configuration files
│   ├── email_config.py.example    # Email configuration template
│   └── email_config.py            # Email configuration (not in git, create from example)
│
├── data/                           # Data files
│   ├── attendance.csv              # Attendance records (auto-generated)
│   └── attendence_excel.xls       # Excel attendance file (auto-generated)
│
├── docs/                           # Documentation
│   ├── EMAIL_SETUP.md             # Email configuration guide
│   ├── GMAIL_SETUP.md             # Gmail-specific setup instructions
│   ├── SETUP_INSTRUCTIONS.md      # Quick setup guide
│   └── PROJECT_STRUCTURE.md       # This file
│
├── scripts/                        # Utility scripts
│   ├── capture_image_from_camera.py  # Camera image capture script
│   └── face recognition code.py      # Face recognition testing script
│
├── static/                         # Static files (CSS, JS, images)
│   ├── css/
│   │   └── style.css              # Main stylesheet
│   ├── js/
│   │   ├── main.js                # Main JavaScript for attendance
│   │   └── admin.js               # Admin panel JavaScript
│   ├── img/
│   │   └── placeholder.png        # Placeholder image
│   └── images/                    # Student face images
│       ├── ANSHU.jpg
│       ├── jatin.png
│       ├── kalpana.png
│       ├── saurav.png
│       └── Shlock.jpg
│
└── templates/                      # HTML templates
    ├── index.html                 # Home/Student attendance page
    ├── admin_login.html           # Admin login page
    ├── forgot_password.html       # Forgot password page
    ├── reset_password.html        # Password reset page
    ├── admin_dashboard.html       # Admin dashboard
    └── emails/                    # Email templates
        └── email_reset_password.html  # Password reset email template
```

## File Descriptions

### Root Files
- **app.py**: Main Flask application with all routes and logic
- **requirements.txt**: Python package dependencies
- **README.md**: Project overview and setup instructions
- **setup_email.bat**: Windows script to quickly configure email settings

### config/
Contains configuration files. The actual `email_config.py` should be created from the example file and is not tracked in git (contains sensitive credentials).

### data/
Contains generated data files:
- CSV and Excel files for attendance records
- These are auto-generated and should not be manually edited

### docs/
All documentation files including setup guides and instructions.

### scripts/
Utility scripts for:
- Testing face recognition
- Capturing images from camera

### static/
All static assets:
- **css/**: Stylesheets
- **js/**: JavaScript files
- **img/**: General images/icons
- **images/**: Student face photos (used for recognition)

### templates/
HTML templates organized by purpose:
- Main pages (index, login, dashboard)
- Email templates in `emails/` subfolder

## Configuration

### Setting Up Email

1. Copy `config/email_config.py.example` to `config/email_config.py`
2. Edit `config/email_config.py` with your email credentials
3. Or use `setup_email.bat` for quick setup

### Running the Application

```bash
python app.py
```

The application will:
- Load email config from `config/email_config.py` or root `email_config.py`
- Read attendance data from `data/attendance.csv`
- Store student images in `static/images/`
- Serve static files from `static/` directory
- Render templates from `templates/` directory

## Notes

- `email_config.py` is in `.gitignore` to protect credentials
- Student images should be placed in `static/images/`
- Attendance records are automatically saved to `data/` directory
- All paths are relative to the project root
