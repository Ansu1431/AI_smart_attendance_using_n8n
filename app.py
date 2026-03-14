from flask import Flask, request, render_template, jsonify, redirect, url_for, session, send_from_directory, flash
from flask_mail import Mail, Message
import os
import io
import base64
import glob
import numpy as np
import sqlite3
import json
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timedelta
from itsdangerous import URLSafeTimedSerializer
import secrets

# Face recognition mode: 'face_recognition' > 'opencv' > 'imagehash'
FACE_RECOG_AVAILABLE = False
OPENCV_AVAILABLE = False
RECOG_MODE = 'imagehash'
_face_cascade = None

try:
    import face_recognition
    FACE_RECOG_AVAILABLE = True
    RECOG_MODE = 'face_recognition'
    print('[Face] Using face_recognition library (best accuracy)')
except Exception as _e:
    print(f'[Face] face_recognition not available: {_e}')
    try:
        import cv2 as _cv2_check
        OPENCV_AVAILABLE = True
        RECOG_MODE = 'opencv'
        print('[Face] Using OpenCV Haar cascade + cosine similarity')
    except Exception as _e2:
        print(f'[Face] OpenCV not available: {_e2}. Falling back to image-hash (low accuracy).')
        RECOG_MODE = 'imagehash'
        from PIL import Image
        import imagehash

from PIL import Image as PILImage

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET', 'change-me')

# Define paths first
BASE_DIR = os.path.dirname(__file__)
PASSWORD_FILE = os.path.join(BASE_DIR, '.admin_password')
DB_PATH = os.path.join(BASE_DIR, 'data', 'attendance.db')
# n8n webhook URLs – read from email_config.py first, fall back to env vars
def _load_n8n_webhooks():
    marks = os.environ.get('N8N_MARKS_WEBHOOK', '').strip()
    alert = os.environ.get('N8N_ALERT_WEBHOOK', '').strip()
    try:
        import email_config as _cfg
        if not marks:
            marks = getattr(_cfg, 'N8N_MARKS_WEBHOOK', '').strip()
        if not alert:
            alert = getattr(_cfg, 'N8N_ALERT_WEBHOOK', '').strip()
    except ImportError:
        try:
            import sys as _sys
            _cfg_path = os.path.join(os.path.dirname(__file__), 'config')
            if _cfg_path not in _sys.path:
                _sys.path.insert(0, _cfg_path)
            import email_config as _cfg2
            if not marks:
                marks = getattr(_cfg2, 'N8N_MARKS_WEBHOOK', '').strip()
            if not alert:
                alert = getattr(_cfg2, 'N8N_ALERT_WEBHOOK', '').strip()
        except ImportError:
            pass
    return marks, alert

N8N_MARKS_WEBHOOK, N8N_ALERT_WEBHOOK = _load_n8n_webhooks()
print(f"[n8n] Marks webhook : {N8N_MARKS_WEBHOOK or '(not set)'}")
print(f"[n8n] Alert webhook : {N8N_ALERT_WEBHOOK or '(not set)'}")
LOW_PERFORMANCE_THRESHOLD = 0.40  # 40% threshold for marks and attendance alerts

# ── WhatsApp (Twilio) config ─────────────────────────────────────────────────
def _load_twilio_config():
    sid   = os.environ.get('TWILIO_ACCOUNT_SID', '').strip()
    token = os.environ.get('TWILIO_AUTH_TOKEN', '').strip()
    from_ = os.environ.get('TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886').strip()
    try:
        import email_config as _cfg
        sid   = sid   or getattr(_cfg, 'TWILIO_ACCOUNT_SID',  '').strip()
        token = token or getattr(_cfg, 'TWILIO_AUTH_TOKEN',   '').strip()
        from_ = getattr(_cfg, 'TWILIO_WHATSAPP_FROM', from_).strip()
    except ImportError:
        pass
    return sid, token, from_

TWILIO_SID, TWILIO_TOKEN, TWILIO_WA_FROM = _load_twilio_config()
TWILIO_AVAILABLE = bool(TWILIO_SID and TWILIO_TOKEN)
print(f"[WhatsApp] Twilio configured: {TWILIO_AVAILABLE}")


def send_whatsapp_message(to_number: str, body: str) -> bool:
    """Send a WhatsApp message via Twilio REST API (no SDK required).
    Returns True on success, False on failure."""
    if not TWILIO_AVAILABLE:
        print('[WhatsApp] Twilio not configured — skipping.')
        return False
    # Strip all whitespace and dashes so "+91 852 755 7996" → "+918527557996"
    to_number = ''.join(to_number.split()).replace('-', '')
    if not to_number.startswith('+'):
        print(f'[WhatsApp] Invalid number (must start with +country code): {to_number}')
        return False
    to_wa = f'whatsapp:{to_number}'
    url = f'https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json'
    data = urllib.parse.urlencode({
        'From': TWILIO_WA_FROM,
        'To':   to_wa,
        'Body': body,
    }).encode('utf-8')
    import base64 as _b64
    credentials = _b64.b64encode(f'{TWILIO_SID}:{TWILIO_TOKEN}'.encode()).decode()
    req = urllib.request.Request(url, data=data, method='POST',
                                  headers={'Authorization': f'Basic {credentials}',
                                           'Content-Type': 'application/x-www-form-urlencoded'})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            print(f'[WhatsApp] Sent to {to_number} — status {resp.status}')
            return True
    except Exception as e:
        print(f'[WhatsApp] Send failed to {to_number}: {e}')
        return False

# Simple admin password (replace or set env var ADMIN_PASSWORD in production)
# Check for password file first, then env var, then default
def get_admin_password():
    if os.path.exists(PASSWORD_FILE):
        try:
            with open(PASSWORD_FILE, 'r') as f:
                return f.read().strip()
        except:
            pass
    return os.environ.get('ADMIN_PASSWORD', 'admin123')

def save_admin_password(password):
    """Save admin password to file"""
    try:
        with open(PASSWORD_FILE, 'w') as f:
            f.write(password.strip())
        return True
    except Exception as e:
        print(f'Error saving password: {e}')
        return False

ADMIN_PASSWORD = get_admin_password()

# Try to load from config file first, then environment variables
# Check root directory first (for backward compatibility), then config directory
try:
    # Try root directory first
    import email_config as email_cfg
    ADMIN_EMAIL = getattr(email_cfg, 'ADMIN_EMAIL', os.environ.get('ADMIN_EMAIL', 'admin@example.com'))
    ADMIN_NAME = getattr(email_cfg, 'ADMIN_NAME', os.environ.get('ADMIN_NAME', 'Admin'))
    app.config['MAIL_SERVER'] = getattr(email_cfg, 'MAIL_SERVER', os.environ.get('MAIL_SERVER', 'smtp.gmail.com'))
    app.config['MAIL_PORT'] = int(getattr(email_cfg, 'MAIL_PORT', os.environ.get('MAIL_PORT', 587)))
    app.config['MAIL_USE_TLS'] = getattr(email_cfg, 'MAIL_USE_TLS', True) if hasattr(email_cfg, 'MAIL_USE_TLS') else (os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true')
    app.config['MAIL_USE_SSL'] = getattr(email_cfg, 'MAIL_USE_SSL', False) if hasattr(email_cfg, 'MAIL_USE_SSL') else (os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true')
    app.config['MAIL_USERNAME'] = getattr(email_cfg, 'MAIL_USERNAME', os.environ.get('MAIL_USERNAME', ''))
    app.config['MAIL_PASSWORD'] = getattr(email_cfg, 'MAIL_PASSWORD', os.environ.get('MAIL_PASSWORD', ''))
    app.config['MAIL_DEFAULT_SENDER'] = getattr(email_cfg, 'MAIL_DEFAULT_SENDER', os.environ.get('MAIL_DEFAULT_SENDER', ADMIN_EMAIL))
    print("[OK] Email configuration loaded from email_config.py")
except ImportError:
    # Try config directory
    try:
        import sys
        config_path = os.path.join(BASE_DIR, 'config')
        if config_path not in sys.path:
            sys.path.insert(0, config_path)
        import email_config as email_cfg
        ADMIN_EMAIL = getattr(email_cfg, 'ADMIN_EMAIL', os.environ.get('ADMIN_EMAIL', 'admin@example.com'))
        ADMIN_NAME = getattr(email_cfg, 'ADMIN_NAME', os.environ.get('ADMIN_NAME', 'Admin'))
        app.config['MAIL_SERVER'] = getattr(email_cfg, 'MAIL_SERVER', os.environ.get('MAIL_SERVER', 'smtp.gmail.com'))
        app.config['MAIL_PORT'] = int(getattr(email_cfg, 'MAIL_PORT', os.environ.get('MAIL_PORT', 587)))
        app.config['MAIL_USE_TLS'] = getattr(email_cfg, 'MAIL_USE_TLS', True) if hasattr(email_cfg, 'MAIL_USE_TLS') else (os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true')
        app.config['MAIL_USE_SSL'] = getattr(email_cfg, 'MAIL_USE_SSL', False) if hasattr(email_cfg, 'MAIL_USE_SSL') else (os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true')
        app.config['MAIL_USERNAME'] = getattr(email_cfg, 'MAIL_USERNAME', os.environ.get('MAIL_USERNAME', ''))
        app.config['MAIL_PASSWORD'] = getattr(email_cfg, 'MAIL_PASSWORD', os.environ.get('MAIL_PASSWORD', ''))
        app.config['MAIL_DEFAULT_SENDER'] = getattr(email_cfg, 'MAIL_DEFAULT_SENDER', os.environ.get('MAIL_DEFAULT_SENDER', ADMIN_EMAIL))
        print("[OK] Email configuration loaded from config/email_config.py")
    except ImportError:
        # Fall back to environment variables
        ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
        ADMIN_NAME = os.environ.get('ADMIN_NAME', 'Admin')
        app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
        app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
        app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
        app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true'
        app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', '')
        app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')
        app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', ADMIN_EMAIL)
        print("[INFO] Using environment variables for email configuration (or create email_config.py)")
    except ImportError:
        # Fall back to environment variables
        ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
        ADMIN_NAME = os.environ.get('ADMIN_NAME', 'Admin')
        app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
        app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
        app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
        app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true'
        app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', '')
        app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')
        app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', ADMIN_EMAIL)
        print("[INFO] Using environment variables for email configuration (or create email_config.py)")
except ImportError:
    # Fall back to environment variables
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
    ADMIN_NAME = os.environ.get('ADMIN_NAME', 'Admin')
    app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true'
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', '')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', ADMIN_EMAIL)
    print("[INFO] Using environment variables for email configuration (or create email_config.py)")

# Initialize Flask-Mail
mail = Mail(app)

# Token serializer for password reset
serializer = URLSafeTimedSerializer(app.secret_key)

IMAGES_DIR = os.path.join(BASE_DIR, 'static', 'images')
ATTENDANCE_CSV = os.path.join(BASE_DIR, 'data', 'attendance.csv')
SCHEDULE_FILE  = os.path.join(BASE_DIR, 'data', 'scheduled_classes.json')


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            student_email TEXT,
            parent_email TEXT,
            student_phone TEXT,
            parent_phone TEXT
        )
        """
    )
    # Add phone columns to existing databases (safe to run multiple times)
    for col in ('student_phone', 'parent_phone'):
        try:
            conn.execute(f"ALTER TABLE students ADD COLUMN {col} TEXT")
        except Exception:
            pass
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS marks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            exam_type TEXT NOT NULL,
            term INTEGER NOT NULL,
            score REAL NOT NULL,
            max_score REAL NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(student_id) REFERENCES students(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            marks_percentage REAL,
            attendance_percentage REAL,
            sent_at TEXT NOT NULL,
            marks_snapshot TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def ensure_student(name: str) -> int:
    conn = get_db_connection()
    row = conn.execute("SELECT id FROM students WHERE name = ?", (name,)).fetchone()
    if row:
        conn.close()
        return row["id"]
    cur = conn.execute("INSERT INTO students (name) VALUES (?)", (name,))
    conn.commit()
    student_id = cur.lastrowid
    conn.close()
    return student_id


def get_student_profile(name: str):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT id, name, student_email, parent_email, student_phone, parent_phone FROM students WHERE name = ?",
        (name,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_student_profile(name: str, student_email: str, parent_email: str,
                            student_phone: str = '', parent_phone: str = '') -> int:
    student_id = ensure_student(name)
    conn = get_db_connection()
    conn.execute(
        "UPDATE students SET student_email=?, parent_email=?, student_phone=?, parent_phone=? WHERE id=?",
        (student_email, parent_email, student_phone or '', parent_phone or '', student_id),
    )
    conn.commit()
    conn.close()
    return student_id


def add_student_mark(name: str, subject: str, exam_type: str, term: int, score: float, max_score: float):
    student_id = ensure_student(name)
    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO marks (student_id, subject, exam_type, term, score, max_score, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (student_id, subject, exam_type, term, score, max_score, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def get_student_marks(name: str):
    profile = get_student_profile(name)
    if not profile:
        return []
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT id, subject, exam_type, term, score, max_score
        FROM marks
        WHERE student_id = ?
        ORDER BY exam_type, term, subject
        """,
        (profile["id"],),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_attendance_summary(name: str):
    count = 0
    last_seen = None
    if os.path.exists(ATTENDANCE_CSV):
        try:
            with open(ATTENDANCE_CSV, 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split(',')
                    if len(parts) >= 3 and parts[0] == name:
                        count += 1
                        last_seen = {"date": parts[1], "time": parts[2]}
        except Exception as e:
            print('Failed to read attendance:', e)
    return {"count": count, "last_seen": last_seen}


def get_total_attendance_days():
    """Return the number of unique class days recorded across all students."""
    dates = set()
    if os.path.exists(ATTENDANCE_CSV):
        try:
            with open(ATTENDANCE_CSV, 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split(',')
                    if len(parts) >= 2 and parts[1]:
                        dates.add(parts[1])
        except Exception as e:
            print('Failed to read attendance days:', e)
    return len(dates)


def get_student_attendance_percentage(name: str):
    """Calculate a student's attendance percentage (attended / total class days)."""
    total_days = get_total_attendance_days()
    if total_days == 0:
        return None
    attended_dates = set()
    if os.path.exists(ATTENDANCE_CSV):
        try:
            with open(ATTENDANCE_CSV, 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split(',')
                    if len(parts) >= 2 and parts[0] == name:
                        attended_dates.add(parts[1])
        except Exception:
            pass
    return len(attended_dates) / total_days


def get_student_marks_percentage(name: str):
    """Calculate a student's overall marks percentage across all recorded marks."""
    marks = get_student_marks(name)
    if not marks:
        return None
    total_score = sum(float(m['score']) for m in marks)
    total_max = sum(float(m['max_score']) for m in marks)
    return (total_score / total_max) if total_max > 0 else None


def check_and_send_low_performance_alert(name: str) -> dict:
    """Check if a student is below the 40% threshold and send alert email + n8n trigger.
    Alert is sent only ONCE per unique marks snapshot — re-sends only if marks actually change."""
    profile = get_student_profile(name)
    if not profile:
        return {'sent': False, 'reason': 'student not found'}

    recipients = []
    if profile.get('student_email'):
        recipients.append(profile['student_email'])
    if profile.get('parent_email'):
        recipients.append(profile['parent_email'])
    if not recipients:
        return {'sent': False, 'reason': 'no email addresses on file'}

    marks_pct = get_student_marks_percentage(name)
    att_pct = get_student_attendance_percentage(name)

    alerts = []
    if marks_pct is not None and marks_pct < LOW_PERFORMANCE_THRESHOLD:
        alerts.append({'type': 'marks', 'percentage': round(marks_pct * 100, 1)})
    if att_pct is not None and att_pct < LOW_PERFORMANCE_THRESHOLD:
        alerts.append({'type': 'attendance', 'percentage': round(att_pct * 100, 1)})

    if not alerts:
        return {'sent': False, 'reason': 'performance above threshold'}

    # Build a snapshot of current marks to detect if anything has changed since last alert
    current_marks = get_student_marks(name)
    marks_snapshot = json.dumps(
        sorted([(m['subject'], m['exam_type'], m['term'], m['score'], m['max_score'])
                for m in current_marks]),
        sort_keys=True
    )

    # Check if we already sent an alert for this exact marks snapshot
    conn = get_db_connection()
    existing = conn.execute(
        """SELECT id FROM alert_log
           WHERE student_name = ? AND marks_snapshot = ?
           ORDER BY sent_at DESC LIMIT 1""",
        (name, marks_snapshot)
    ).fetchone()
    conn.close()

    if existing:
        return {'sent': False, 'reason': 'alert already sent for current marks — no change detected'}

    # Trigger n8n outbound alert webhook if configured
    if N8N_ALERT_WEBHOOK:
        try:
            payload = json.dumps({
                'student': name,
                'student_email': profile.get('student_email', ''),
                'parent_email': profile.get('parent_email', ''),
                'alerts': alerts,
                'marks_percentage': round(marks_pct * 100, 1) if marks_pct is not None else None,
                'attendance_percentage': round(att_pct * 100, 1) if att_pct is not None else None,
                'threshold': int(LOW_PERFORMANCE_THRESHOLD * 100),
                'triggered_at': datetime.utcnow().isoformat(),
            }).encode('utf-8')
            req = urllib.request.Request(
                N8N_ALERT_WEBHOOK,
                data=payload,
                headers={'Content-Type': 'application/json'},
                method='POST',
            )
            urllib.request.urlopen(req, timeout=10)
            print(f'[n8n] Low-performance alert triggered for {name}')
        except Exception as e:
            print(f'[n8n alert webhook failed for {name}]: {e}')

    # Send email alert
    try:
        if not app.config.get('MAIL_USERNAME') or not app.config.get('MAIL_PASSWORD'):
            return {'sent': False, 'reason': 'email not configured', 'alerts': alerts}
        attendance_summary = get_attendance_summary(name)
        msg = Message(
            subject=f'⚠️ Low Performance Alert – {name}',
            recipients=recipients,
            html=render_template(
                'emails/email_low_performance.html',
                student=profile,
                marks=current_marks,
                attendance=attendance_summary,
                alerts=alerts,
                marks_percentage=round(marks_pct * 100, 1) if marks_pct is not None else None,
                attendance_percentage=round(att_pct * 100, 1) if att_pct is not None else None,
                threshold=int(LOW_PERFORMANCE_THRESHOLD * 100),
            ),
        )
        mail.send(msg)
        # Record in alert_log so this exact snapshot is never emailed again
        conn = get_db_connection()
        conn.execute(
            """INSERT INTO alert_log (student_name, alert_type, marks_percentage,
               attendance_percentage, sent_at, marks_snapshot)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                name,
                ','.join(a['type'] for a in alerts),
                round(marks_pct * 100, 1) if marks_pct is not None else None,
                round(att_pct * 100, 1) if att_pct is not None else None,
                datetime.utcnow().isoformat(),
                marks_snapshot,
            )
        )
        conn.commit()
        conn.close()
        print(f'[Alert] Low-performance email sent for {name} → {recipients}')

        # ── WhatsApp alerts via Twilio ────────────────────────────────
        # Build detailed marks breakdown
        marks_lines = []
        for m in current_marks:
            pct = round(float(m['score']) / float(m['max_score']) * 100, 1) if float(m['max_score']) > 0 else 0.0
            marks_lines.append(
                f"  • {m['subject']} - {m['exam_type']} ({m['term']}): "
                f"{m['score']}/{m['max_score']} ({pct}%)"
            )
        marks_block = '\n'.join(marks_lines) if marks_lines else '  No marks recorded.'

        # Build alert summary lines
        alert_lines = []
        for a in alerts:
            label = 'Marks' if a['type'] == 'marks' else 'Attendance'
            alert_lines.append(f"  ⚠️ {label}: {a['percentage']}% (threshold: {int(LOW_PERFORMANCE_THRESHOLD*100)}%)")

        att_count = attendance_summary.get('count', 0)
        marks_pct_display  = f"{round(marks_pct * 100, 1)}%" if marks_pct is not None else 'N/A'
        att_pct_display    = f"{round(att_pct  * 100, 1)}%" if att_pct  is not None else 'N/A'

        wa_body = (
            f"⚠️ *Low Performance Alert*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Student: *{name}*\n\n"
            f"📊 *Performance Summary*\n"
            f"  Overall Marks:    {marks_pct_display}\n"
            f"  Attendance Rate:  {att_pct_display}\n"
            f"  Classes Attended: {att_count}\n\n"
            f"🚨 *Issues Detected:*\n"
            + '\n'.join(alert_lines) + "\n\n"
            f"📋 *Marks Breakdown:*\n"
            + marks_block + "\n\n"
            f"Please take action immediately.\n"
            f"— AI Smart Attendance System"
        )
        wa_sent = []
        for phone_field in ('student_phone', 'parent_phone'):
            number = (profile.get(phone_field) or '').strip()
            if number:
                ok = send_whatsapp_message(number, wa_body)
                if ok:
                    wa_sent.append(number)

        return {'sent': True, 'alerts': alerts, 'recipients': recipients, 'whatsapp_sent': wa_sent}
    except Exception as e:
        print(f'[Alert email failed for {name}]: {e}')
        return {'sent': False, 'reason': str(e), 'alerts': alerts}


def build_ai_summary(name: str, marks, attendance_summary):
    if not marks:
        return f"{name} has no marks recorded yet. Attendance count: {attendance_summary['count']}."

    totals = {}
    for mark in marks:
        key = (mark["exam_type"], mark["term"])
        entry = totals.setdefault(key, {"score": 0.0, "max": 0.0})
        entry["score"] += float(mark["score"])
        entry["max"] += float(mark["max_score"])

    parts = []
    for (exam_type, term), agg in totals.items():
        percent = (agg["score"] / agg["max"] * 100) if agg["max"] else 0
        parts.append(f"{exam_type.title()} term {term}: {agg['score']:.1f}/{agg['max']:.1f} ({percent:.1f}%)")

    last_seen = attendance_summary.get("last_seen")
    last_text = ""
    if last_seen:
        last_text = f" Last attendance: {last_seen['date']} {last_seen['time']}."
    return f"{name}'s performance summary: " + "; ".join(parts) + f". Attendance count: {attendance_summary['count']}." + last_text


def sanitize_name(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip().replace(' ', '_')


# ── OpenCV face helpers ─────────────────────────────────────────────────────

def _get_face_cascade():
    """Load (and cache) the OpenCV Haar cascade for face detection."""
    global _face_cascade
    if _face_cascade is None:
        import cv2
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        _face_cascade = cv2.CascadeClassifier(cascade_path)
    return _face_cascade


def _extract_face_vector(img_rgb_np):
    """Detect the largest face in an RGB numpy array using Haar cascade.
    Returns a unit-normalised 1-D float32 vector (128×128 grayscale, histogram-equalised),
    or None if no face is found."""
    import cv2
    cascade = _get_face_cascade()
    gray = cv2.cvtColor(img_rgb_np, cv2.COLOR_RGB2GRAY)

    # Try strict first, then relax params if no face found
    for (sf, mn, ms) in [(1.1, 5, (50, 50)), (1.05, 3, (30, 30)), (1.15, 2, (20, 20))]:
        faces = cascade.detectMultiScale(gray, scaleFactor=sf, minNeighbors=mn, minSize=ms)
        if len(faces) > 0:
            break

    if len(faces) == 0:
        return None

    # Use the largest detected face
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])

    # Add a small margin around the face box
    margin = int(max(w, h) * 0.15)
    x1 = max(0, x - margin)
    y1 = max(0, y - margin)
    x2 = min(img_rgb_np.shape[1], x + w + margin)
    y2 = min(img_rgb_np.shape[0], y + h + margin)

    face_gray = gray[y1:y2, x1:x2]
    face_resized = cv2.resize(face_gray, (128, 128))
    face_eq = cv2.equalizeHist(face_resized)

    vec = face_eq.flatten().astype(np.float32)
    norm = np.linalg.norm(vec)
    return (vec / norm) if norm > 0 else None


def load_known_faces():
    """Load known faces and build a lookup dict:
      face_recognition mode : name -> 128-d encoding (np.array)
      opencv mode           : name -> 16384-d unit vector (np.float32)
      imagehash mode        : name -> imagehash.phash object
    """
    encodings = {}
    for path in glob.glob(os.path.join(IMAGES_DIR, '*')):
        if not os.path.isfile(path):
            continue
        filename = os.path.basename(path)
        name, _ = os.path.splitext(filename)
        try:
            if RECOG_MODE == 'face_recognition':
                img = face_recognition.load_image_file(path)
                faces = face_recognition.face_encodings(img)
                if faces:
                    encodings[name] = faces[0]
            elif RECOG_MODE == 'opencv':
                import cv2
                img_bgr = cv2.imread(path)
                if img_bgr is None:
                    pil = PILImage.open(path).convert('RGB')
                    img_bgr = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
                img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
                vec = _extract_face_vector(img_rgb)
                if vec is not None:
                    encodings[name] = vec
                    print(f'[Face] Loaded: {name}')
                else:
                    print(f'[Face] No face detected in {path} — re-upload a clearer photo')
            else:  # imagehash
                pil = PILImage.open(path).convert('RGB')
                encodings[name] = imagehash.phash(pil)
        except Exception as e:
            print(f'[Face] Skipping {path}: {e}')
    print(f'[Face] Loaded {len(encodings)} student(s) in mode={RECOG_MODE}')
    return encodings


# Global cache of known faces
KNOWN_FACES = load_known_faces()
init_db()


ATTENDANCE_COOLDOWN_MINUTES = 60  # minimum gap (minutes) between marks for the same student (1 hour)

# ── Class Schedule for CSE/CST_6_A ──────────────────────────────────────────
# Format: {'start': 'HH:MM', 'end': 'HH:MM', 'subject': '...', 'room': '...'}
# Applied every weekday (Mon–Sat). Day index 0=Mon … 5=Sat, 6=Sun
CLASS_SCHEDULE = [
    {'start': '09:20', 'end': '10:10', 'subject': 'ADBMS',                 'room': 'A-304'},
    {'start': '10:10', 'end': '11:50', 'subject': 'Advanced Java Lab',     'room': 'A-105'},
    {'start': '11:50', 'end': '12:40', 'subject': 'Compiler Design (CD)',   'room': 'A-304'},
    # 12:40 – 13:30 → LUNCH (no entry)
    {'start': '13:30', 'end': '14:20', 'subject': 'Compiler Design Lab',   'room': 'A-104'},
    {'start': '14:20', 'end': '15:10', 'subject': 'Compiler Design (CD)',   'room': 'A-304'},
]

def load_scheduled_classes():
    """Load admin-scheduled class overrides from JSON file."""
    try:
        if os.path.exists(SCHEDULE_FILE):
            with open(SCHEDULE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f'[Scheduler] Failed to load schedule: {e}')
    return {}

def save_scheduled_classes(data: dict):
    """Persist admin-scheduled classes to JSON file."""
    os.makedirs(os.path.dirname(SCHEDULE_FILE), exist_ok=True)
    with open(SCHEDULE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def get_current_class():
    """Return the class slot currently running.
    Checks admin-scheduled overrides first, then falls back to CLASS_SCHEDULE."""
    now = datetime.now()
    if now.weekday() == 6:          # Sunday – no classes
        return None
    today = str(now.date())
    now_hhmm = now.strftime('%H:%M')

    # Check admin-scheduled overrides for today
    scheduled = load_scheduled_classes()
    if today in scheduled:
        for slot in scheduled[today]:
            if slot.get('start', '') <= now_hhmm < slot.get('end', ''):
                return slot
        # If admin scheduled today (even if empty), don't fall back to default
        return None

    # Fall back to default weekly schedule
    for slot in CLASS_SCHEDULE:
        if slot['start'] <= now_hhmm < slot['end']:
            return slot
    return None

def get_schedule_for_date(date_str: str) -> list:
    """Return scheduled slots for a specific date (admin-overridden or default)."""
    scheduled = load_scheduled_classes()
    if date_str in scheduled:
        return scheduled[date_str]
    # Return default weekly schedule as template
    return CLASS_SCHEDULE

def record_attendance(name: str, subject: str = ''):
    """Append an attendance record to CSV (name,date,time,subject).
    Enforces a per-student cooldown of ATTENDANCE_COOLDOWN_MINUTES.
    Returns dict: {'recorded': bool, 'cooldown_remaining': int seconds (0 if just recorded)}
    """
    try:
        ts = datetime.now()
        today = str(ts.date())
        os.makedirs(os.path.dirname(ATTENDANCE_CSV), exist_ok=True)

        # Find the most-recent entry for this student today
        last_time = None
        if os.path.exists(ATTENDANCE_CSV):
            with open(ATTENDANCE_CSV, 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split(',')
                    if len(parts) >= 3 and parts[0] == name and parts[1] == today:
                        try:
                            t = datetime.strptime(f"{parts[1]} {parts[2]}", "%Y-%m-%d %H:%M:%S")
                            if last_time is None or t > last_time:
                                last_time = t
                        except ValueError:
                            pass

        if last_time is not None:
            elapsed = (ts - last_time).total_seconds()
            cooldown_secs = ATTENDANCE_COOLDOWN_MINUTES * 60
            if elapsed < cooldown_secs:
                remaining = int(cooldown_secs - elapsed)
                return {'recorded': False, 'cooldown_remaining': remaining}

        # Auto-detect subject from schedule if not provided
        if not subject:
            slot = get_current_class()
            subject = slot['subject'] if slot else ''

        # Escape commas in subject for CSV safety
        safe_subject = subject.replace(',', ';')
        entry = f'{name},{today},{ts.strftime("%H:%M:%S")},{safe_subject}\n'
        with open(ATTENDANCE_CSV, 'a', encoding='utf-8') as f:
            f.write(entry)
        return {'recorded': True, 'cooldown_remaining': 0, 'subject': subject}
    except Exception as e:
        print('Failed to record attendance:', e)
        return {'recorded': False, 'cooldown_remaining': 0}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/current_class')
def api_current_class():
    """Return the class currently in session, or null."""
    slot = get_current_class()
    if slot:
        now = datetime.now()
        end_h, end_m = map(int, slot['end'].split(':'))
        end_dt = now.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
        mins_left = max(0, int((end_dt - now).total_seconds() // 60))
        return jsonify({
            'active': True,
            'subject': slot['subject'],
            'room': slot.get('room', ''),
            'start': slot['start'],
            'end': slot['end'],
            'mins_remaining': mins_left,
        })
    return jsonify({'active': False})


# ── Class Scheduler APIs ─────────────────────────────────────────────────────

@app.route('/api/admin/get_schedule')
def api_get_schedule():
    if not session.get('admin'):
        return jsonify({'error': 'unauthorized'}), 401
    date_str = request.args.get('date', '').strip()
    if not date_str:
        date_str = str((datetime.now() + timedelta(days=1)).date())
    slots = get_schedule_for_date(date_str)
    is_overridden = date_str in load_scheduled_classes()
    return jsonify({'date': date_str, 'slots': slots, 'overridden': is_overridden})


@app.route('/api/admin/save_schedule', methods=['POST'])
def api_save_schedule():
    if not session.get('admin'):
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    date_str = data.get('date', '').strip()
    slots    = data.get('slots', [])
    if not date_str:
        return jsonify({'error': 'date required'}), 400
    # Validate slots
    clean = []
    for s in slots:
        if s.get('start') and s.get('end') and s.get('subject'):
            clean.append({
                'start':   s['start'],
                'end':     s['end'],
                'subject': s['subject'].strip(),
                'room':    s.get('room', '').strip(),
            })
    scheduled = load_scheduled_classes()
    if clean:
        scheduled[date_str] = clean
    elif date_str in scheduled:
        del scheduled[date_str]   # remove override → fall back to default
    save_scheduled_classes(scheduled)
    return jsonify({'ok': True, 'date': date_str, 'slots_saved': len(clean)})


@app.route('/api/admin/clear_schedule', methods=['POST'])
def api_clear_schedule():
    if not session.get('admin'):
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    date_str = data.get('date', '').strip()
    if not date_str:
        return jsonify({'error': 'date required'}), 400
    scheduled = load_scheduled_classes()
    if date_str in scheduled:
        del scheduled[date_str]
        save_scheduled_classes(scheduled)
    return jsonify({'ok': True})


# ── Student Profile (public, QR destination) ─────────────────────────────────

@app.route('/profile/<name>')
def student_profile(name):
    """Public profile page — opened when a student scans their QR code."""
    profile = get_student_profile(name)
    if not profile:
        return render_template('student_profile.html', not_found=True, name=name)
    marks = get_student_marks(name)
    att   = get_attendance_summary(name)
    marks_pct = get_student_marks_percentage(name)
    att_pct   = get_student_attendance_percentage(name)
    return render_template(
        'student_profile.html',
        not_found=False,
        profile=profile,
        marks=marks,
        attendance=att,
        marks_pct=round(marks_pct * 100, 1) if marks_pct is not None else None,
        att_pct=round(att_pct * 100, 1)     if att_pct   is not None else None,
        threshold=int(LOW_PERFORMANCE_THRESHOLD * 100),
    )


@app.route('/admin')
def admin_login():
    return render_template('admin_login.html')


@app.route('/admin/login', methods=['POST'])
def do_admin_login():
    password = request.form.get('password', '')
    current_password = get_admin_password()
    if password == current_password:
        session['admin'] = True
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_login.html', error='Invalid password')


@app.route('/admin/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        
        # Check if email matches admin email
        if email.lower() == ADMIN_EMAIL.lower():
            # Generate reset token (valid for 1 hour)
            token = serializer.dumps(email, salt='password-reset-salt')
            reset_url = url_for('reset_password', token=token, _external=True)
            
            # Send email
            try:
                # Test email configuration
                if not app.config.get('MAIL_USERNAME') or not app.config.get('MAIL_PASSWORD'):
                    raise ValueError('Email username or password not configured')
                
                msg = Message(
                    subject='Password Reset Request - Attendance System',
                    recipients=[ADMIN_EMAIL],
                    html=render_template('emails/email_reset_password.html', 
                                       reset_url=reset_url, 
                                       admin_name=ADMIN_NAME,
                                       expiry_hours=1)
                )
                mail.send(msg)
                print(f"[SUCCESS] Password reset email sent to {ADMIN_EMAIL}")
                return render_template('forgot_password.html', 
                                     success='Password reset link has been sent to your email address. Please check your inbox.')
            except Exception as e:
                error_msg = str(e)
                print(f'[ERROR] Email sending failed: {error_msg}')
                print(f'[DEBUG] Mail config - Server: {app.config.get("MAIL_SERVER")}, Port: {app.config.get("MAIL_PORT")}')
                print(f'[DEBUG] Mail config - Username: {app.config.get("MAIL_USERNAME")}, TLS: {app.config.get("MAIL_USE_TLS")}')
                
                # Provide more helpful error message
                if 'authentication failed' in error_msg.lower() or 'invalid credentials' in error_msg.lower():
                    error_display = 'Email authentication failed. For Gmail, you need to use an App Password instead of your regular password. Please check EMAIL_SETUP.md for instructions.'
                elif '535' in error_msg or 'smtp' in error_msg.lower():
                    error_display = f'SMTP error: {error_msg}. Please verify your email credentials and SMTP settings.'
                else:
                    error_display = f'Failed to send email: {error_msg}. Please check your email configuration.'
                
                return render_template('forgot_password.html', error=error_display)
        else:
            # Don't reveal if email exists or not (security best practice)
            return render_template('forgot_password.html', 
                                 success='If the email address exists, a password reset link has been sent.')
    
    return render_template('forgot_password.html')


@app.route('/admin/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        # Verify token (valid for 1 hour)
        email = serializer.loads(token, salt='password-reset-salt', max_age=3600)
    except Exception as e:
        return render_template('reset_password.html', error='Invalid or expired reset link. Please request a new one.', invalid_token=True)
    
    if request.method == 'POST':
        new_password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        if not new_password:
            return render_template('reset_password.html', error='Password cannot be empty.', token=token)
        
        if new_password != confirm_password:
            return render_template('reset_password.html', error='Passwords do not match.', token=token)
        
        if len(new_password) < 6:
            return render_template('reset_password.html', error='Password must be at least 6 characters long.', token=token)
        
        # Update password
        if save_admin_password(new_password):
            global ADMIN_PASSWORD
            ADMIN_PASSWORD = new_password
            return render_template('reset_password.html', 
                                 success='Password has been successfully reset! You can now login with your new password.',
                                 token=None, reset_success=True)
        else:
            return render_template('reset_password.html', 
                                 error='Failed to save password. Please contact your system administrator.',
                                 token=token)
    
    if 'reset_success' in request.args:
        return render_template('reset_password.html', 
                             success='Password reset successful! You can now login with your new password.',
                             token=None, reset_success=True)
    return render_template('reset_password.html', token=token)


def _image_from_bytes(file_bytes):
    """Return image in the format expected by the active RECOG_MODE:
      face_recognition : RGB numpy array  (via face_recognition.load_image_file)
      opencv           : RGB numpy array  (via PIL→numpy)
      imagehash        : PIL Image
    """
    try:
        pil = PILImage.open(io.BytesIO(file_bytes)).convert('RGB')
        if RECOG_MODE == 'face_recognition':
            return np.array(pil)
        elif RECOG_MODE == 'opencv':
            return np.array(pil)
        else:
            return pil
    except Exception as e:
        print(f'[Face] _image_from_bytes error: {e}')
        return PILImage.open(io.BytesIO(file_bytes)).convert('RGB')


@app.route('/api/verify', methods=['POST'])
def api_verify():
    # Accept form-data file or JSON with base64 image
    file = request.files.get('image')
    img = None
    if file:
        img = _image_from_bytes(file.read())
    else:
        payload = request.get_json(silent=True) or {}
        b64 = payload.get('image')
        if b64:
            header, _, data = b64.partition(',')
            file_bytes = base64.b64decode(data or b64)
            img = _image_from_bytes(file_bytes)

    if img is None:
        return jsonify({'error': 'No image provided', 'match': False}), 400

    if not KNOWN_FACES:
        return jsonify({'error': 'No registered students', 'match': False}), 400

    # ── Mode 1: face_recognition ──────────────────────────────────────────
    if RECOG_MODE == 'face_recognition':
        faces = face_recognition.face_encodings(img)
        if not faces:
            return jsonify({'error': 'No face found', 'match': False}), 200
        face = faces[0]
        names = list(KNOWN_FACES.keys())
        encs  = list(KNOWN_FACES.values())
        distances = face_recognition.face_distance(encs, face)
        best_idx = int(np.argmin(distances))
        match = distances[best_idx] < 0.50
        name  = names[best_idx] if match else 'Unknown'

    # ── Mode 2: OpenCV Haar cascade + cosine similarity ───────────────────
    elif RECOG_MODE == 'opencv':
        vec = _extract_face_vector(img)  # img is already RGB numpy array
        if vec is None:
            return jsonify({'error': 'No face found', 'match': False}), 200

        best_name = None
        best_sim  = -1.0
        for n, kv in KNOWN_FACES.items():
            if kv is None:
                continue
            sim = float(np.dot(vec, kv))
            if sim > best_sim:
                best_sim  = sim
                best_name = n

        # Cosine similarity ≥ 0.82 → match  (tune this if you get false positives/negatives)
        COSINE_THRESHOLD = 0.82
        match = (best_sim >= COSINE_THRESHOLD) and (best_name is not None)
        name  = best_name if match else 'Unknown'
        # store similarity as pseudo-distance for response
        distances = [1.0 - best_sim]
        best_idx  = 0

    # ── Mode 3: imagehash fallback ────────────────────────────────────────
    else:
        ph        = imagehash.phash(img)
        best_name = None
        best_dist = 999
        for n, h in KNOWN_FACES.items():
            d = ph - h
            if d < best_dist:
                best_dist = d
                best_name = n
        match    = best_dist <= 10
        name     = best_name if match else 'Unknown'
        distances = [best_dist]
        best_idx  = 0

    # ── Record & respond ──────────────────────────────────────────────────
    newly_recorded    = False
    cooldown_remaining = 0
    if match:
        result = record_attendance(name)
        newly_recorded     = result['recorded']
        cooldown_remaining = result['cooldown_remaining']
        ensure_student(name)

    dist_val = float(distances[best_idx]) if RECOG_MODE != 'imagehash' else int(distances[0])
    current_slot = get_current_class()
    response = {
        'name': name,
        'match': bool(match),
        'distance': dist_val,
        'newly_recorded': newly_recorded,
        'cooldown_remaining': cooldown_remaining,  # seconds; >0 means blocked by time limit
        'current_subject': current_slot['subject'] if current_slot else None,
    }
    if match:
        profile            = get_student_profile(name)
        marks              = get_student_marks(name)
        attendance_summary = get_attendance_summary(name)
        response.update({"student": profile, "marks": marks, "attendance": attendance_summary})
    return jsonify(response)


@app.route('/api/admin/add_student', methods=['POST'])
def api_add_student():
    if not session.get('admin'):
        return jsonify({'error': 'unauthorized'}), 401
    name = request.form.get('name', '').strip()
    file = request.files.get('image')
    if not name:
        return jsonify({'error': 'name required'}), 400
    safe = sanitize_name(name)
    os.makedirs(IMAGES_DIR, exist_ok=True)
    if file:
        ext = os.path.splitext(file.filename)[1] or '.png'
        dest = os.path.join(IMAGES_DIR, f"{safe}{ext}")
        file.save(dest)
    else:
        # no uploaded file: copy placeholder image so student has a thumbnail
        placeholder = os.path.join(BASE_DIR, 'static', 'img', 'placeholder.png')
        dest = os.path.join(IMAGES_DIR, f"{safe}.png")
        try:
            if os.path.exists(placeholder):
                import shutil
                shutil.copyfile(placeholder, dest)
            else:
                # create a tiny blank image as fallback
                from PIL import Image as PILImg
                img = PILImg.new('RGB', (200, 200), color=(200, 200, 200))
                img.save(dest)
        except Exception as e:
            print('Failed to create placeholder image:', e)
    # Save optional profile fields
    student_email  = request.form.get('student_email', '').strip()
    parent_email   = request.form.get('parent_email',  '').strip()
    student_phone  = request.form.get('student_phone', '').strip()
    parent_phone   = request.form.get('parent_phone',  '').strip()
    # reload
    global KNOWN_FACES
    KNOWN_FACES = load_known_faces()
    ensure_student(safe)
    if student_email or parent_email or student_phone or parent_phone:
        update_student_profile(safe, student_email, parent_email, student_phone, parent_phone)
    return jsonify({'ok': True, 'students': list(KNOWN_FACES.keys())})


@app.route('/api/admin/update_student', methods=['POST'])
def api_update_student():
    if not session.get('admin'):
        return jsonify({'error': 'unauthorized'}), 401
    name           = request.form.get('name',           '').strip()
    student_email  = request.form.get('student_email',  '').strip()
    parent_email   = request.form.get('parent_email',   '').strip()
    student_phone  = request.form.get('student_phone',  '').strip()
    parent_phone   = request.form.get('parent_phone',   '').strip()
    if not name:
        return jsonify({'error': 'name required'}), 400
    update_student_profile(name, student_email, parent_email, student_phone, parent_phone)
    return jsonify({'ok': True})


@app.route('/api/admin/add_mark', methods=['POST'])
def api_add_mark():
    if not session.get('admin'):
        return jsonify({'error': 'unauthorized'}), 401
    name = request.form.get('name', '').strip()
    subject = request.form.get('subject', '').strip()
    exam_type = request.form.get('exam_type', '').strip().lower()
    term = request.form.get('term', '').strip()
    score = request.form.get('score', '').strip()
    max_score = request.form.get('max_score', '').strip()
    if not name or not subject or not exam_type or not term or not score or not max_score:
        return jsonify({'error': 'all fields required'}), 400
    if exam_type not in ('sessional', 'semester'):
        return jsonify({'error': 'exam_type must be sessional or semester'}), 400
    try:
        term_val = int(term)
        score_val = float(score)
        max_val = float(max_score)
    except ValueError:
        return jsonify({'error': 'term, score, and max_score must be numeric'}), 400
    add_student_mark(name, subject, exam_type, term_val, score_val, max_val)
    # Alert only sent when admin explicitly clicks "Check & Send Alerts"
    return jsonify({'ok': True})


@app.route('/api/admin/student_details')
def api_student_details():
    if not session.get('admin'):
        return jsonify({'error': 'unauthorized'}), 401
    name = request.args.get('name', '').strip()
    if not name:
        return jsonify({'error': 'name required'}), 400
    profile = get_student_profile(name)
    marks = get_student_marks(name)
    attendance_summary = get_attendance_summary(name)
    return jsonify({'student': profile, 'marks': marks, 'attendance': attendance_summary})


@app.route('/api/admin/send_marks', methods=['POST'])
def api_send_marks():
    if not session.get('admin'):
        return jsonify({'error': 'unauthorized'}), 401
    name = request.form.get('name', '').strip()
    if not name:
        return jsonify({'error': 'name required'}), 400
    profile = get_student_profile(name)
    if not profile:
        return jsonify({'error': 'student not found'}), 404
    recipients = []
    if profile.get('parent_email'):
        recipients.append(profile['parent_email'])
    if profile.get('student_email'):
        recipients.append(profile['student_email'])
    if not recipients:
        return jsonify({'error': 'no recipient emails set for this student'}), 400

    marks = get_student_marks(name)
    attendance_summary = get_attendance_summary(name)
    summary = build_ai_summary(name, marks, attendance_summary)

    try:
        if not app.config.get('MAIL_USERNAME') or not app.config.get('MAIL_PASSWORD'):
            raise ValueError('Email username or password not configured')
        msg = Message(
            subject=f'Marks Summary - {name}',
            recipients=recipients,
            html=render_template(
                'emails/email_marks_summary.html',
                student=profile,
                marks=marks,
                attendance=attendance_summary,
                summary=summary,
            ),
        )
        mail.send(msg)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def sync_marks_from_webhook():
    if not N8N_MARKS_WEBHOOK:
        raise ValueError('N8N_MARKS_WEBHOOK is not configured')

    try:
        with urllib.request.urlopen(N8N_MARKS_WEBHOOK, timeout=20) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
    except urllib.error.URLError as e:
        raise ValueError(f'Failed to reach webhook: {e}')
    except json.JSONDecodeError:
        raise ValueError('Webhook response is not valid JSON')

    students = payload.get('students', []) if isinstance(payload, dict) else []
    if not isinstance(students, list):
        raise ValueError('Webhook response must include a students array')

    conn = get_db_connection()
    conn.execute('DELETE FROM marks')
    student_count = 0
    mark_count = 0

    for student in students:
        if not isinstance(student, dict):
            continue
        name = str(student.get('name', '')).strip()
        if not name:
            continue
        student_email = str(student.get('student_email') or '').strip()
        parent_email = str(student.get('parent_email') or '').strip()

        row = conn.execute('SELECT id FROM students WHERE name = ?', (name,)).fetchone()
        if row:
            student_id = row['id']
            conn.execute(
                'UPDATE students SET student_email = ?, parent_email = ? WHERE id = ?',
                (student_email, parent_email, student_id),
            )
        else:
            cur = conn.execute(
                'INSERT INTO students (name, student_email, parent_email) VALUES (?, ?, ?)',
                (name, student_email, parent_email),
            )
            student_id = cur.lastrowid
        student_count += 1

        marks = student.get('marks', []) if isinstance(student, dict) else []
        for mark in marks:
            if not isinstance(mark, dict):
                continue
            subject = str(mark.get('subject', '')).strip()
            exam_type = str(mark.get('exam_type', '')).strip().lower()
            if exam_type == 'seasonal':
                exam_type = 'sessional'
            if not subject or exam_type not in ('sessional', 'semester'):
                continue
            try:
                term = int(mark.get('term', 1))
                score = float(mark.get('score', 0))
                max_score = float(mark.get('max_score', 0))
            except (TypeError, ValueError):
                continue
            conn.execute(
                """
                INSERT INTO marks (student_id, subject, exam_type, term, score, max_score, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (student_id, subject, exam_type, term, score, max_score, datetime.utcnow().isoformat()),
            )
            mark_count += 1

    conn.commit()
    conn.close()

    # Alerts are NOT sent automatically on sync.
    # Admin must explicitly click "Check & Send Alerts" to trigger emails.
    return {
        'students': student_count,
        'marks': mark_count,
        'synced_at': datetime.utcnow().isoformat()
    }


@app.route('/api/admin/sync_marks')
def api_sync_marks():
    if not session.get('admin'):
        return jsonify({'error': 'unauthorized'}), 401
    try:
        result = sync_marks_from_webhook()
        return jsonify({'ok': True, **result})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/admin/remove_student', methods=['POST'])
def api_remove_student():
    if not session.get('admin'):
        return jsonify({'error': 'unauthorized'}), 401
    name = request.form.get('name', '')
    if not name:
        return jsonify({'error': 'name required'}), 400
    safe = sanitize_name(name)
    removed = False
    for path in glob.glob(os.path.join(IMAGES_DIR, f"{safe}.*")):
        try:
            os.remove(path)
            removed = True
        except Exception as e:
            print('remove error', e)
    global KNOWN_FACES
    KNOWN_FACES = load_known_faces()
    return jsonify({'ok': True, 'removed': removed, 'students': list(KNOWN_FACES.keys())})


@app.route('/api/admin/check_alerts', methods=['POST'])
def api_check_alerts():
    """Manually trigger low-performance checks for all students or a specific one."""
    if not session.get('admin'):
        return jsonify({'error': 'unauthorized'}), 401
    name = request.form.get('name', '').strip()
    conn = get_db_connection()
    if name:
        student_names = [name]
    else:
        rows = conn.execute('SELECT name FROM students').fetchall()
        student_names = [r['name'] for r in rows]
    conn.close()

    results = []
    alerts_sent = 0
    for sname in student_names:
        marks_pct = get_student_marks_percentage(sname)
        att_pct = get_student_attendance_percentage(sname)
        result = check_and_send_low_performance_alert(sname)
        if result.get('sent'):
            alerts_sent += 1
        results.append({
            'name': sname,
            'marks_percentage': round(marks_pct * 100, 1) if marks_pct is not None else None,
            'attendance_percentage': round(att_pct * 100, 1) if att_pct is not None else None,
            'below_threshold': bool(result.get('alerts')),
            'alert_sent': result.get('sent', False),
        })
    return jsonify({'ok': True, 'checked': len(results), 'alerts_sent': alerts_sent, 'results': results})


@app.route('/api/admin/performance_summary')
def api_performance_summary():
    """Return performance summary for all students (marks %, attendance %)."""
    if not session.get('admin'):
        return jsonify({'error': 'unauthorized'}), 401
    conn = get_db_connection()
    rows = conn.execute('SELECT name FROM students').fetchall()
    conn.close()
    summary = []
    for row in rows:
        sname = row['name']
        marks_pct = get_student_marks_percentage(sname)
        att_pct = get_student_attendance_percentage(sname)
        summary.append({
            'name': sname,
            'marks_percentage': round(marks_pct * 100, 1) if marks_pct is not None else None,
            'attendance_percentage': round(att_pct * 100, 1) if att_pct is not None else None,
            'marks_below_threshold': (marks_pct is not None and marks_pct < LOW_PERFORMANCE_THRESHOLD),
            'attendance_below_threshold': (att_pct is not None and att_pct < LOW_PERFORMANCE_THRESHOLD),
        })
    return jsonify({'ok': True, 'threshold': int(LOW_PERFORMANCE_THRESHOLD * 100), 'students': summary})


@app.route('/images/<path:filename>')
def serve_image(filename):
    # Serve images from the images directory
    return send_from_directory(IMAGES_DIR, filename)


def read_attendance(deduplicate=True):
    """Read attendance CSV. If deduplicate=True, keeps only the first record per (student, date)."""
    rows = []
    seen = set()
    if os.path.exists(ATTENDANCE_CSV):
        try:
            with open(ATTENDANCE_CSV, 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split(',')
                    if len(parts) >= 3 and parts[0] and parts[1]:
                        key = (parts[0], parts[1])
                        if deduplicate and key in seen:
                            continue
                        seen.add(key)
                        subject = parts[3] if len(parts) >= 4 else ''
                        rows.append({
                            'name': parts[0],
                            'date': parts[1],
                            'time': parts[2],
                            'subject': subject,
                        })
        except Exception as e:
            print('Failed to read attendance:', e)
    return rows


@app.route('/api/admin/today_summary')
def api_today_summary():
    """Return which registered students are present/absent today."""
    if not session.get('admin'):
        return jsonify({'error': 'unauthorized'}), 401
    today = str(datetime.now().date())
    # Students present today (unique names)
    present = set()
    if os.path.exists(ATTENDANCE_CSV):
        try:
            with open(ATTENDANCE_CSV, 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split(',')
                    if len(parts) >= 2 and parts[1] == today:
                        present.add(parts[0])
        except Exception:
            pass
    # All registered students
    all_students = []
    for path in sorted(glob.glob(os.path.join(IMAGES_DIR, '*'))):
        if os.path.isfile(path):
            name, _ = os.path.splitext(os.path.basename(path))
            all_students.append(name)
    absent = [s for s in all_students if s not in present]
    return jsonify({
        'today': today,
        'present': sorted(list(present)),
        'absent': absent,
        'present_count': len(present),
        'total': len(all_students),
    })


@app.route('/api/admin/export_attendance')
def api_export_attendance():
    """Download attendance as a clean CSV file (deduplicated, one entry per student per day)."""
    if not session.get('admin'):
        return jsonify({'error': 'unauthorized'}), 401
    date_filter = request.args.get('date', '').strip()  # optional YYYY-MM-DD filter
    rows = read_attendance(deduplicate=True)
    if date_filter:
        rows = [r for r in rows if r['date'] == date_filter]
    lines = ['Name,Date,Time,Subject,Status']
    for r in rows:
        lines.append(f"{r['name']},{r['date']},{r['time']},{r.get('subject','')},Present")
    csv_bytes = '\n'.join(lines).encode('utf-8')
    from flask import Response
    filename = f"attendance_{date_filter or 'all'}.csv"
    return Response(
        csv_bytes,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )


@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    # Build student list from actual files in IMAGES_DIR so we can show correct extensions
    students = []
    for path in sorted(glob.glob(os.path.join(IMAGES_DIR, '*'))):
        if os.path.isfile(path):
            filename = os.path.basename(path)
            name, _ext = os.path.splitext(filename)
            students.append({'name': name, 'filename': filename})
    attendance = read_attendance()
    return render_template('admin_dashboard.html', students=students, attendance=attendance)


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

