import os
import io
import json
import logging
import tempfile
from datetime import datetime
import urllib.parse

import qrcode
import gspread
from flask import (Flask, render_template, request,
                   send_file, redirect, url_for, session)
from oauth2client.service_account import ServiceAccountCredentials
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

# ── Logging (visible in Render logs) ──────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "chatra-somaj-secret-2024")

# ── CONFIGURATION ─────────────────────────────────────────────────────────────
SHEET_NAME   = os.environ.get("SHEET_NAME",   "Blood Donor Database")
ORG_NAME     = os.environ.get("ORG_NAME",     "Chatra Somaj")
ORG_SUBTITLE = os.environ.get("ORG_SUBTITLE", "Blood Donation Camp")
APP_URL      = os.environ.get("APP_URL",      "")   # set this on Render!
CREDS_FILE   = "credentials.json"
ADMIN_PASS   = os.environ.get("ADMIN_PASSWORD", "chatra2024")

SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

# Column indices (0-based, after header row)
COL = dict(
    timestamp=0, name=1, mobile=2, blood_group=3,
    don_date=4, don_id=5, units=6, age=7, gender=8, address=9
)
# ──────────────────────────────────────────────────────────────────────────────


# ── GOOGLE SHEETS ─────────────────────────────────────────────────────────────

def _make_creds():
    """Build ServiceAccountCredentials from env var or local file."""
    raw = os.environ.get("GOOGLE_CREDS_JSON", "").strip()
    if raw:
        log.info("Loading Google credentials from GOOGLE_CREDS_JSON env var")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"GOOGLE_CREDS_JSON is not valid JSON: {e}")
        with tempfile.NamedTemporaryFile(
                mode='w', suffix='.json', delete=False) as f:
            json.dump(data, f)
            tmp = f.name
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name(tmp, SCOPE)
        finally:
            os.unlink(tmp)
        return creds

    if os.path.exists(CREDS_FILE):
        log.info("Loading Google credentials from credentials.json")
        return ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)

    raise RuntimeError(
        "No Google credentials found. "
        "Set GOOGLE_CREDS_JSON env var on Render, or place credentials.json locally."
    )


def get_sheet():
    creds  = _make_creds()
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).sheet1


def _row_to_donor(row):
    def cell(key):
        idx = COL[key]
        return row[idx].strip() if len(row) > idx else ""
    return {
        "name":        cell("name"),
        "mobile":      cell("mobile"),
        "blood_group": cell("blood_group"),
        "don_date":    cell("don_date"),
        "don_id":      cell("don_id"),
        "units":       cell("units") or "1",
        "age":         cell("age"),
        "gender":      cell("gender"),
        "address":     cell("address"),
        "timestamp":   cell("timestamp"),
    }


def _normalise_mobile(m):
    return m.strip().replace(" ", "").replace("+91", "").replace("-", "")


def find_donor(mobile: str):
    target = _normalise_mobile(mobile)
    sheet  = get_sheet()
    rows   = sheet.get_all_values()
    for row in rows[1:]:
        if len(row) > COL["mobile"]:
            if _normalise_mobile(row[COL["mobile"]]) == target:
                return _row_to_donor(row)
    return None


# ── PDF GENERATION ────────────────────────────────────────────────────────────

def _make_qr(data: str) -> io.BytesIO:
    qr = qrcode.QRCode(version=2, box_size=6, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#B91C1C", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _base_url():
    """Return the live base URL, auto-detecting if APP_URL is not set."""
    if APP_URL:
        return APP_URL.rstrip("/")
    try:
        return request.host_url.rstrip("/")
    except RuntimeError:
        return "http://localhost:5000"


def generate_certificate_pdf(donor: dict) -> io.BytesIO:
    buf    = io.BytesIO()
    W, H   = landscape(A4)
    c      = canvas.Canvas(buf, pagesize=landscape(A4))
    inner  = 24   # border inset

    # Background
    c.setFillColor(colors.HexColor("#FFFAF9"))
    c.rect(0, 0, W, H, fill=1, stroke=0)

    # Outer red border
    c.setStrokeColor(colors.HexColor("#B91C1C"))
    c.setLineWidth(3)
    c.rect(inner - 6, inner - 6,
           W - 2*(inner-6), H - 2*(inner-6), fill=0, stroke=1)

    # Inner pale border
    c.setStrokeColor(colors.HexColor("#FCA5A5"))
    c.setLineWidth(1)
    c.rect(inner, inner, W - 2*inner, H - 2*inner, fill=0, stroke=1)

    # Top red banner
    bh = 88
    c.setFillColor(colors.HexColor("#B91C1C"))
    c.rect(inner, H - inner - bh, W - 2*inner, bh, fill=1, stroke=0)

    # Org name in banner
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 27)
    c.drawCentredString(W/2, H - inner - 38, ORG_NAME.upper())
    c.setFont("Helvetica", 12)
    c.drawCentredString(W/2, H - inner - 60, ORG_SUBTITLE)

    # Certificate title
    title_y = H - inner - bh - 44
    c.setFillColor(colors.HexColor("#7F1D1D"))
    c.setFont("Helvetica-Bold", 21)
    c.drawCentredString(W/2, title_y, "CERTIFICATE OF APPRECIATION")
    c.setStrokeColor(colors.HexColor("#B91C1C"))
    c.setLineWidth(1.5)
    c.line(W/2 - 145, title_y - 8, W/2 + 145, title_y - 8)

    # Certify text
    c.setFillColor(colors.HexColor("#374151"))
    c.setFont("Helvetica", 11)
    c.drawCentredString(W/2, title_y - 28, "This is to certify that")

    # Donor name
    name_y = title_y - 64
    c.setFillColor(colors.HexColor("#B91C1C"))
    c.setFont("Helvetica-Bold", 32)
    c.drawCentredString(W/2, name_y, donor["name"])
    c.setStrokeColor(colors.HexColor("#FCA5A5"))
    c.setLineWidth(1)
    c.line(W/2 - 170, name_y - 6, W/2 + 170, name_y - 6)

    # Appreciation lines
    c.setFillColor(colors.HexColor("#374151"))
    c.setFont("Helvetica", 11)
    c.drawCentredString(W/2, name_y - 24,
        "has generously donated blood and demonstrated an extraordinary act of humanity.")
    c.drawCentredString(W/2, name_y - 40,
        "We express our heartfelt gratitude for this noble contribution that can save many precious lives.")

    # Detail table
    dy     = name_y - 72
    lx     = W/2 - 235
    rx     = W/2 + 10
    row_h  = 22

    def left_detail(label, val, y):
        c.setFillColor(colors.HexColor("#6B7280"))
        c.setFont("Helvetica", 9.5)
        c.drawString(lx, y, label + ":")
        c.setFillColor(colors.HexColor("#111827"))
        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(lx + 100, y, str(val))

    def right_detail(label, val, y):
        c.setFillColor(colors.HexColor("#6B7280"))
        c.setFont("Helvetica", 9.5)
        c.drawString(rx, y, label + ":")
        c.setFillColor(colors.HexColor("#111827"))
        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(rx + 100, y, str(val))

    left_detail("Blood Group",  donor["blood_group"],            dy)
    right_detail("Donation Date", donor["don_date"],             dy)
    left_detail("Donation ID",  donor["don_id"],                 dy - row_h)
    right_detail("Units Donated", donor["units"] + " unit(s)",  dy - row_h)
    left_detail("Donor Age",
                (donor["age"] + " years") if donor["age"] else "—",
                dy - 2*row_h)
    right_detail("Gender", donor["gender"] or "—",              dy - 2*row_h)

    # Thank-you quote
    q_y = dy - 3*row_h - 8
    c.setFillColor(colors.HexColor("#B91C1C"))
    c.setFont("Helvetica-BoldOblique", 11.5)
    c.drawCentredString(W/2, q_y,
        '"Thank you for your noble act of donating blood and helping save lives."')

    # ── SIGNATURE SECTION ────────────────────────────────────
    sig_y  = inner + 32
    sig_lx = inner + 30

    sig_img_path = os.path.join("static", "signature.png")
    if os.path.exists(sig_img_path):
        try:
            c.drawImage(ImageReader(sig_img_path),
                        sig_lx, sig_y + 22,
                        width=190, height=46,
                        preserveAspectRatio=True, mask='auto')
        except Exception as e:
            log.warning("Could not draw signature image: %s", e)

    c.setStrokeColor(colors.HexColor("#374151"))
    c.setLineWidth(0.8)
    c.line(sig_lx, sig_y + 20, sig_lx + 195, sig_y + 20)
    c.setFillColor(colors.HexColor("#374151"))
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(sig_lx + 97, sig_y + 7, "Authorised Signatory")
    c.setFont("Helvetica", 9)
    c.drawCentredString(sig_lx + 97, sig_y - 4, ORG_NAME)

    # Issue date (centre)
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.HexColor("#6B7280"))
    c.drawCentredString(W/2, sig_y + 10,
                        "Issued on: " + datetime.now().strftime("%d %B %Y"))

    # ── QR CODE ──────────────────────────────────────────────
    # Space in "TEST 01" → encoded as "TEST%2001" in the URL
    encoded_id = urllib.parse.quote(donor['don_id'].strip(), safe='')
    verify_url = f"{_base_url()}/verify/{encoded_id}"
    log.info("QR verify URL: %s", verify_url)

    qr_buf  = _make_qr(verify_url)
    qr_img  = ImageReader(qr_buf)
    qr_size = 76
    qr_x    = W - inner - 48 - qr_size
    c.drawImage(qr_img, qr_x, sig_y - 6, qr_size, qr_size)
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#6B7280"))
    c.drawCentredString(qr_x + qr_size/2, sig_y - 14, "Scan to verify")

    # Bottom red strip
    c.setFillColor(colors.HexColor("#B91C1C"))
    c.rect(inner, inner, W - 2*inner, 9, fill=1, stroke=0)

    c.save()
    buf.seek(0)
    return buf


# ── ROUTES ────────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET", "POST"])
def index():
    error = None
    if request.method == "POST":
        mobile = request.form.get("mobile", "").strip()
        clean  = _normalise_mobile(mobile)
        if not clean:
            error = "Please enter your mobile number."
        elif not clean.isdigit():
            error = "Mobile number should contain digits only."
        elif len(clean) < 10:
            error = "Please enter a valid 10-digit mobile number."
        else:
            return redirect(url_for("certificate", mobile=clean))
    return render_template("index.html", error=error, org_name=ORG_NAME)


@app.route("/certificate/<path:mobile>")
def certificate(mobile):
    try:
        donor = find_donor(mobile)
    except Exception as e:
        log.error("Sheet lookup error: %s", e)
        return render_template("error.html",
                               mobile=mobile,
                               org_name=ORG_NAME,
                               sheet_error=str(e)), 500

    if donor is None:
        return render_template("error.html",
                               mobile=mobile,
                               org_name=ORG_NAME,
                               sheet_error=None)
    session["donor"] = donor
    return render_template("certificate.html", donor=donor, org_name=ORG_NAME)


@app.route("/download")
def download():
    donor = session.get("donor")
    if donor is None:
        mobile = request.args.get("mobile", "").strip()
        if mobile:
            try:
                donor = find_donor(mobile)
            except Exception as e:
                log.error("Sheet lookup error on download: %s", e)
                return f"Error fetching record: {e}", 500

    if donor is None:
        return redirect(url_for("index"))

    try:
        pdf_buf  = generate_certificate_pdf(donor)
        filename = f"BloodDonation_{donor['don_id'] or donor['mobile']}.pdf"
        return send_file(pdf_buf,
                         mimetype="application/pdf",
                         as_attachment=True,
                         download_name=filename)
    except Exception as e:
        log.error("PDF generation error: %s", e)
        return f"Error generating PDF: {e}", 500


@app.route("/verify/<path:don_id>")
def verify(don_id):
    # URL-decode in case the ID was encoded (e.g. spaces as %20)
    don_id_clean = urllib.parse.unquote(don_id).strip()
    log.info("Verifying donation ID: '%s'", don_id_clean)
    try:
        sheet = get_sheet()
        rows  = sheet.get_all_values()
        donor = None
        for row in rows[1:]:
            if len(row) > COL["don_id"]:
                sheet_id = row[COL["don_id"]].strip()
                # Match exactly, or with spaces collapsed
                if sheet_id == don_id_clean or                    sheet_id.replace(" ", "") == don_id_clean.replace(" ", ""):
                    donor = _row_to_donor(row)
                    log.info("Verified: found donor '%s'", donor['name'])
                    break
        if donor is None:
            log.warning("Verify: no match for don_id '%s'", don_id_clean)
    except Exception as e:
        log.error("Verify sheet error: %s", e)
        donor = None
 
    now = datetime.now().strftime("%d %B %Y, %I:%M %p")
    return render_template("verify.html",
                           donor=donor, don_id=don_id_clean,
                           org_name=ORG_NAME, now=now)
 

@app.route("/health")
def health():
    """Render uses this to check the app is alive."""
    status = {"status": "ok", "org": ORG_NAME}
    # Quick credential check
    has_creds = bool(os.environ.get("GOOGLE_CREDS_JSON")) or \
                os.path.exists(CREDS_FILE)
    status["credentials"] = "found" if has_creds else "MISSING"
    return status, 200


@app.route("/debug")
def debug():
    """TEMPORARY — shows what env vars are set. Remove after fixing."""
    import sys
    info = {
        "python":           sys.version,
        "SHEET_NAME":       SHEET_NAME,
        "ORG_NAME":         ORG_NAME,
        "APP_URL":          APP_URL or "(not set — will auto-detect)",
        "GOOGLE_CREDS_JSON": "SET ✅" if os.environ.get("GOOGLE_CREDS_JSON") else "NOT SET ❌",
        "credentials.json": "exists ✅" if os.path.exists(CREDS_FILE) else "not found",
        "static/signature.png": "exists ✅" if os.path.exists("static/signature.png") else "not uploaded yet",
        "cwd": os.getcwd(),
        "files_in_cwd": os.listdir("."),
    }
    rows = "".join(f"<tr><td><b>{k}</b></td><td>{v}</td></tr>" for k, v in info.items())
    return f"""
    <html><body style='font-family:monospace;padding:24px'>
    <h2>🩸 Debug Info</h2>
    <table border=1 cellpadding=8>{rows}</table>
    <p style='color:red'>⚠️ Remove the /debug route once your app is working!</p>
    <p><a href='/health'>/health</a> &nbsp; <a href='/'>Home</a></p>
    </body></html>
    """


# ── ADMIN: SIGNATURE UPLOAD ───────────────────────────────────────────────────

@app.route("/admin/signature", methods=["GET", "POST"])
def upload_signature():
    msg     = None
    success = False

    if request.method == "POST":
        pwd = request.form.get("password", "")
        if pwd != ADMIN_PASS:
            msg = "Wrong password."
        elif "signature" not in request.files or \
             request.files["signature"].filename == "":
            msg = "No file selected."
        else:
            f   = request.files["signature"]
            ext = f.filename.rsplit(".", 1)[-1].lower()
            if ext not in {"png", "jpg", "jpeg"}:
                msg = "Only PNG or JPG allowed."
            else:
                try:
                    from PIL import Image as PILImage
                    os.makedirs("static", exist_ok=True)
                    img = PILImage.open(f).convert("RGBA")
                    img.save(os.path.join("static", "signature.png"))
                    msg     = "Signature uploaded! New certificates will include it."
                    success = True
                except Exception as e:
                    msg = f"Upload failed: {e}"

    has_sig = os.path.exists(os.path.join("static", "signature.png"))
    return render_template("admin_signature.html",
                           msg=msg, success=success,
                           has_sig=has_sig, org_name=ORG_NAME)


# ── GLOBAL ERROR HANDLERS ─────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html",
                           mobile="",
                           org_name=ORG_NAME,
                           sheet_error=None), 404


@app.errorhandler(500)
def server_error(e):
    log.error("500 error: %s", e)
    return render_template("error.html",
                           mobile="",
                           org_name=ORG_NAME,
                           sheet_error=str(e)), 500


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)