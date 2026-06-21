# 🩸 Chatra Somaj — Blood Donation Certificate System

A complete Flask web app where blood donors scan a QR code at the camp,
enter their mobile number, and instantly download a professional PDF certificate.

---

## 📁 Project Structure

```
blood-cert/
├── app.py                     ← Main Flask application (all routes + PDF logic)
├── generate_qr.py             ← Run ONCE after deploy to make the camp QR
├── requirements.txt           ← Python dependencies
├── Procfile                   ← Tells Render how to start the app
├── render.yaml                ← Render auto-deploy config
├── credentials.json           ← ⚠️ YOUR Google service account key (never commit!)
├── credentials.json.example   ← Shows what credentials.json should look like
├── .gitignore                 ← Excludes credentials.json and qr.png from git
├── templates/
│   ├── index.html             ← Home page (mobile number entry form)
│   ├── certificate.html       ← Certificate preview + download button
│   ├── error.html             ← Not found / server error page (shows debug info)
│   ├── verify.html            ← QR scan verification page
│   └── admin_signature.html   ← Admin page to upload signature image
└── static/
    └── signature.png          ← Uploaded via /admin/signature (not committed to git)
```

---

## 🚀 Full Setup & Deployment Guide

### STEP 1 — Create Your Google Sheet

1. Go to [sheets.google.com](https://sheets.google.com) and create a new sheet
2. Name it **exactly**: `Blood Donor Database` (case-sensitive)
3. In **Row 1**, add these headers in this exact order:

```
Timestamp | Name | Mobile | Blood Group | Donation Date | Donation ID | Units | Age | Gender | Address
```

4. Add one test row to verify everything works:

```
19-06-2026 | Test Donor | 9999999999 | O+ | 19-06-2026 | TEST001 | 1 | 25 | Male | Kolkata
```

> ⚠️ Column order matters. The code reads columns by position (0–9).
> If your sheet has columns in a different order, update the `COL` dictionary in `app.py`.

---

### STEP 2 — Google Cloud: Enable APIs & Create Service Account

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (or select an existing one)
3. In the search bar, search and **Enable** both:
   - `Google Sheets API`
   - `Google Drive API`
4. Go to **IAM & Admin → Service Accounts**
5. Click **Create Service Account**
   - Name: `blood-cert-bot` (any name)
   - Click **Create and Continue** → skip optional steps → **Done**
6. Click the service account you just created → go to **Keys** tab
7. Click **Add Key → Create new key → JSON** → Download
8. Rename the downloaded file to `credentials.json`
9. Place it in the root of your project folder

**Share your Google Sheet with the service account:**

1. Open `credentials.json` — copy the `client_email` value
   (looks like: `blood-cert-bot@your-project.iam.gserviceaccount.com`)
2. Open your Google Sheet → click **Share**
3. Paste the email → set role to **Editor** → click **Share**

> Without this sharing step, the app cannot read your sheet and will crash.

---

### STEP 3 — Run Locally (Test Before Deploying)

```bash
# Go into the project folder
cd blood-cert

# Create a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install all dependencies
pip install -r requirements.txt

# Make sure credentials.json is in this folder (from Step 2)

# Start the app
python app.py
```

Open [http://localhost:5000](http://localhost:5000)

Test it: enter mobile number `9999999999` (your test row) → should show certificate → download PDF.

If it works locally, you're ready to deploy.

---

### STEP 4 — Push to GitHub

```bash
cd blood-cert
git init
git add .
git commit -m "Chatra Somaj blood donation certificate system"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/blood-cert.git
git push -u origin main
```

> ✅ `credentials.json` is in `.gitignore` so it will NOT be pushed to GitHub.
> Never remove it from `.gitignore`.

---

### STEP 5 — Deploy on Render

**5a. Create the web service:**

1. Go to [render.com](https://render.com) → Sign up / Log in with GitHub
2. Click **New → Web Service**
3. Select your `blood-cert` repository
4. Configure:

| Field | Value |
|---|---|
| Name | `blood-certificate` |
| Branch | `main` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn app:app` |
| Instance Type | Free |

5. Click **Create Web Service**

**5b. Add environment variables (critical):**

After the service is created, go to **Environment** tab and add:

| Key | Value |
|---|---|
| `GOOGLE_CREDS_JSON` | Paste the **entire contents** of your `credentials.json` file |
| `APP_URL` | `https://blood-certificate.onrender.com` |
| `SHEET_NAME` | `Blood Donor Database` |
| `ADMIN_PASSWORD` | Any password you choose (for signature upload) |

**How to paste GOOGLE_CREDS_JSON correctly:**

1. Open `credentials.json` in a text editor (Notepad, VS Code)
2. Press `Ctrl+A` → `Ctrl+C` to copy everything
3. In Render → Environment → paste as the value for `GOOGLE_CREDS_JSON`
4. The value must start with `{` and end with `}` — make sure nothing is cut off

> ⚠️ This is the most common cause of Internal Server Error on Render.
> If the JSON is incomplete or has extra characters, the app will crash on every request.

**5c. Deploy:**

Render will auto-deploy when you push to GitHub.
Wait 2–3 minutes for the build to finish.
Check the **Logs** tab — you should see `Gunicorn booted successfully`.

---

### STEP 6 — Verify Your Deployment

Visit these URLs after deploy:

| URL | What it should show |
|---|---|
| `https://blood-certificate.onrender.com/` | Home page with mobile number form |
| `https://blood-certificate.onrender.com/health` | `{"status": "ok", "credentials": "found"}` |
| `https://blood-certificate.onrender.com/debug` | Full debug info — env vars, files, Python version |

> If `/health` shows `"credentials": "MISSING"` → your `GOOGLE_CREDS_JSON` is not set correctly.
> Open `/debug` to see exactly what's wrong.

---

### STEP 7 — Generate the Camp QR Code

After your app is live, run this once on your local machine:

```bash
python generate_qr.py https://blood-certificate.onrender.com
```

This saves `static/qr.png` — **print this and display it at the donation camp.**

Donors scan this QR → opens your app → enter mobile → get certificate.

---

### STEP 8 — Upload Your Signature

To add a real signature to the PDF certificate:

1. Sign on white paper with a black pen
2. Take a clear photo of it
3. Go to [remove.bg](https://www.remove.bg) (free) → upload → download the transparent PNG
4. Go to: `https://blood-certificate.onrender.com/admin/signature`
5. Upload the PNG → enter your admin password → done

All new certificates will show your actual signature above the line.

---

## 🔧 Troubleshooting

### Internal Server Error on Render

**Step 1 — Check Render logs:**
Render dashboard → your service → **Logs** tab → look for red error lines

**Step 2 — Visit the debug page:**
`https://blood-certificate.onrender.com/debug`

This shows exactly which env vars are set and which are missing.

**Most common causes:**

| Error in logs | Fix |
|---|---|
| `GOOGLE_CREDS_JSON is not valid JSON` | Re-paste the full contents of credentials.json — make sure nothing is cut off |
| `SpreadsheetNotFound` | Sheet name doesn't match exactly, OR sheet not shared with service account email |
| `No Google credentials found` | `GOOGLE_CREDS_JSON` env var is not set on Render |
| `Invalid grant` / `credentials expired` | Delete service account key, create a new one, update `GOOGLE_CREDS_JSON` |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` locally and push again |
| Certificate page loads but download gives 404 | You have old `app.py` — replace with the latest version |

### QR Code on PDF Doesn't Work

The QR encodes your live app URL. Make sure `APP_URL` env var is set correctly on Render:
```
APP_URL = https://blood-certificate.onrender.com
```
If `APP_URL` is not set, the app auto-detects the URL from the request — this also works
but it's safer to set it explicitly.

### App is Slow to Load (First Request)

This is normal on Render's **free tier** — the app sleeps after 15 minutes of inactivity
and takes 30–60 seconds to wake up on the first request.

Fix: Upgrade to Render **Starter plan ($7/month)** for always-on service.
Or use [UptimeRobot](https://uptimerobot.com) (free) to ping your `/health` endpoint
every 10 minutes to keep it awake.

---

## 📋 Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `GOOGLE_CREDS_JSON` | ✅ Yes (on Render) | — | Full JSON contents of credentials.json |
| `APP_URL` | Recommended | Auto-detected | Your Render URL e.g. `https://blood-certificate.onrender.com` |
| `SHEET_NAME` | No | `Blood Donor Database` | Google Sheet name (must match exactly) |
| `ORG_NAME` | No | `Chatra Somaj` | Organisation name on certificate |
| `ORG_SUBTITLE` | No | `Blood Donation Camp` | Subtitle in banner |
| `ADMIN_PASSWORD` | No | `chatra2024` | Password for `/admin/signature` |
| `SECRET_KEY` | No | Built-in default | Flask session secret key |

---

## 🔗 All Routes

| URL | Method | Purpose |
|---|---|---|
| `/` | GET, POST | Home — mobile number entry |
| `/certificate/<mobile>` | GET | Certificate preview page |
| `/download?mobile=<mobile>` | GET | Download PDF certificate |
| `/verify/<don_id>` | GET | QR scan verification (linked from PDF) |
| `/admin/signature` | GET, POST | Upload signature image |
| `/health` | GET | Health check (use for UptimeRobot) |
| `/debug` | GET | Debug info — remove in production |

---

## 🗺️ How the Whole System Works

```
Volunteer fills Google Form
         ↓
Data stored in Google Sheet
         ↓
Donor scans QR at camp
         ↓
Opens mobile number form
         ↓
Enters their mobile number
         ↓
Flask searches Google Sheet
         ↓
      Found?
     /      \
   Yes        No
    ↓          ↓
Show cert    Error page
preview      (with help)
    ↓
Download PDF
(with QR + signature)
    ↓
Donor scans QR on PDF
    ↓
/verify page confirms
certificate is genuine
```

---

## 📱 Future Upgrades (Planned)

- [ ] WhatsApp PDF delivery via Twilio
- [ ] SMS confirmation via MSG91
- [ ] Auto-generate Donation ID
- [ ] Admin dashboard with donation analytics
- [ ] Duplicate donor detection
- [ ] Multi-camp support

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| Backend | Python / Flask |
| Database | Google Sheets (via gspread) |
| PDF Generation | ReportLab |
| QR Codes | qrcode + Pillow |
| Frontend | Bootstrap 5 + custom CSS |
| Hosting | Render (free tier) |
| Auth | Google Service Account (oauth2client) |

---

*Built with ❤️ for Chatra Somaj blood donation camps.*