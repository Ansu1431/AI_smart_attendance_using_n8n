# n8n Integration Guide — AI Smart Attendance System

This guide explains how to connect n8n to your Flask attendance website using the two provided workflow JSON files.

---

## Overview

There are **two n8n workflows** that work with your system:

| Workflow File | Purpose |
|---|---|
| `n8n_marks_sync_workflow.json` | Reads marks from Google Sheets and syncs them to Flask |
| `n8n_alert_workflow.json` | Receives low-performance alerts from Flask and sends emails + logs to Sheets |

---

## Step 1 — Install & Run n8n

**Option A: Cloud (easiest)**
Sign up at [n8n.cloud](https://n8n.cloud) — free tier available.

**Option B: Self-hosted (Docker)**
```bash
docker run -it --rm \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  n8nio/n8n
```
Then open: `http://localhost:5678`

---

## Step 2 — Import the Workflows

1. Open n8n → click **"New Workflow"**
2. Click the **menu (⋮)** → **Import from File**
3. Import `n8n_marks_sync_workflow.json`
4. Repeat for `n8n_alert_workflow.json`

---

## Step 3 — Set Up Google Sheets Credentials

1. Go to **n8n Settings → Credentials → New**
2. Select **"Google Sheets OAuth2 API"**
3. Follow the OAuth setup instructions
4. In each workflow, click the Google Sheets nodes and select your credentials
5. In the **"Read Google Sheet"** node, paste your **Google Sheet ID** (from the sheet URL: `https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit`)

**Required Google Sheet columns (Sheet1):**

| Column | Example |
|---|---|
| name | Anshu |
| student_email | anshu@email.com |
| parent_email | parent@email.com |
| subject | Mathematics |
| exam_type | sessional OR semester |
| term | 1 |
| score | 35 |
| max_score | 100 |

---

## Step 4 — Set Up SMTP Email (Alert Workflow)

1. Go to **n8n Settings → Credentials → New**
2. Select **"SMTP"**
3. Fill in your Gmail settings:
   - Host: `smtp.gmail.com`
   - Port: `587`
   - User: `your@gmail.com`
   - Password: **App Password** (not your regular password — see Gmail → Security → App Passwords)
4. In the **"Send Alert Email"** node, select this credential
5. Update `fromEmail` to your address

---

## Step 5 — Get the Webhook URLs

### Marks Sync Webhook (N8N_MARKS_WEBHOOK)
1. In the `Marks Sync` workflow, click **"Manual Sync Webhook"** node
2. Copy the **Production URL** shown (e.g. `https://your-n8n.app.n8n.cloud/webhook/sync-marks`)

### Alert Webhook (N8N_ALERT_WEBHOOK)
1. In the `Alert Handler` workflow, click **"Receive Alert from Flask"** node
2. Copy the **Production URL** (e.g. `https://your-n8n.app.n8n.cloud/webhook/attendance-alert`)

---

## Step 6 — Configure Flask Environment Variables

Add these to your Flask server environment. You can create a `.env` file or set them directly:

**Windows (PowerShell):**
```powershell
$env:N8N_MARKS_WEBHOOK = "https://your-n8n.app.n8n.cloud/webhook/sync-marks"
$env:N8N_ALERT_WEBHOOK = "https://your-n8n.app.n8n.cloud/webhook/attendance-alert"
```

**Linux/Mac:**
```bash
export N8N_MARKS_WEBHOOK="https://your-n8n.app.n8n.cloud/webhook/sync-marks"
export N8N_ALERT_WEBHOOK="https://your-n8n.app.n8n.cloud/webhook/attendance-alert"
```

**Or create a `.env` file and use `python-dotenv`:**
```
N8N_MARKS_WEBHOOK=https://your-n8n.app.n8n.cloud/webhook/sync-marks
N8N_ALERT_WEBHOOK=https://your-n8n.app.n8n.cloud/webhook/attendance-alert
```

---

## Step 7 — Activate the Workflows

1. In each workflow, click the **"Activate"** toggle (top right)
2. Both workflows must be **active** for webhooks to work

---

## Step 8 — Test the Connection

**Test Marks Sync:**
1. In the admin dashboard, click **"Sync from Sheet"**
   — Flask will call your `N8N_MARKS_WEBHOOK` → n8n reads Google Sheets → returns marks JSON

**Test Alerts:**
1. Add a student with email, add a mark below 40%
   — Flask auto-triggers `N8N_ALERT_WEBHOOK` → n8n sends email to student + parent

---

## Data Flow Summary

```
[Student Face Scan]
       ↓
[Face Recognition] → [Flask App]
       ↓
[SQLite Database] ←── [n8n Marks Sync (via Google Sheets)]
       ↓
[Student Dashboard]  [Admin Panel]
                          ↓
              [Marks below 40%?]
                          ↓ YES
              [n8n Alert Webhook]
                          ↓
            [Email → Student + Parent]
            [Log → Google Sheets "Alerts Log"]
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| "N8N_MARKS_WEBHOOK is not configured" | Set the env var and restart Flask |
| Sync returns empty students | Check Google Sheet column names match exactly |
| Alert emails not sending | Verify Gmail App Password and SMTP credentials in n8n |
| Webhook 404 error | Make sure the workflow is **Activated** in n8n |
| Flask can't reach n8n | Make sure n8n is running and accessible from Flask's server |
