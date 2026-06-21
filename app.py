import os
import io
import json
import qrcode
import gspread
from flask import Flask, render_template, request, send_file, redirect, url_for, session
from oauth2client.service_account import ServiceAccountCredentials
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from datetime import datetime
import tempfile

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "chatra-somaj-blood-cert-secret-2024")

# ─────────────────────────────────────────────
# CONFIGURATION  — edit these values
# ─────────────────────────────────────────────
SHEET_NAME      = "Blood Donor Database"
ORG_NAME        = "Chatra Somaj"
ORG_SUBTITLE    = "Blood Donation Camp"
APP_URL         = os.environ.get("APP_URL", "https://blood-certificate.onrender.com")
CREDS_FILE      = "credentials.json"

SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

COL_TIMESTAMP    = 0
COL_NAME         = 1
COL_MOBILE       = 2
COL_BLOOD_GROUP  = 3
COL_DON_DATE     = 4
COL_DON_ID       = 5
COL_UNITS        = 6
COL_AGE          = 7
COL_GENDER       = 8
COL_ADDRESS      = 9
# ─────────────────────────────────────────────


def get_sheet():
    """Connect to Google Sheets — works both locally and on Render."""
    creds_json = os.environ.get("GOOGLE_CREDS_JSON")
    if creds_json:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(creds_json)
            tmp_path = f.name
        creds = ServiceAccountCredentials.from_json_keyfile_name(tmp_path, SCOPE)
        os.unlink(tmp_path)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).sheet1


def find_donor(mobile: str):
    """Search for a donor by mobile number. Returns dict or None."""
    mobile = mobile.strip().replace(" ", "").replace("+91", "")
    sheet = get_sheet()
    records = sheet.get_all_values()

    for row in records[1:]:   # skip header
        if len(row) > COL_MOBILE:
            sheet_mobile = row[COL_MOBILE].strip().replace(" ", "").replace("+91", "")
            if sheet_mobile == mobile:
                return {
                    "timestamp":   row[COL_TIMESTAMP]   if len(row) > COL_TIMESTAMP   else "",
                    "name":        row[COL_NAME]         if len(row) > COL_NAME        else "",
                    "mobile":      row[COL_MOBILE]       if len(row) > COL_MOBILE      else "",
                    "blood_group": row[COL_BLOOD_GROUP]  if len(row) > COL_BLOOD_GROUP else "",
                    "don_date":    row[COL_DON_DATE]     if len(row) > COL_DON_DATE    else "",
                    "don_id":      row[COL_DON_ID]       if len(row) > COL_DON_ID      else "",
                    "units":       row[COL_UNITS]        if len(row) > COL_UNITS       else "1",
                    "age":         row[COL_AGE]          if len(row) > COL_AGE         else "",
                    "gender":      row[COL_GENDER]       if len(row) > COL_GENDER      else "",
                    "address":     row[COL_ADDRESS]      if len(row) > COL_ADDRESS     else "",
                }
    return None


def make_qr(data: str) -> io.BytesIO:
    qr = qrcode.QRCode(version=2, box_size=6, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#B91C1C", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def generate_certificate_pdf(donor: dict) -> io.BytesIO:
    """Generate a landscape A4 PDF certificate."""
    buf = io.BytesIO()
    W, H = landscape(A4)
    c = canvas.Canvas(buf, pagesize=landscape(A4))

    # BACKGROUND
    c.setFillColor(colors.HexColor("#FFFAF9"))
    c.rect(0, 0, W, H, fill=1, stroke=0)

    # OUTER BORDER
    border_margin = 18
    c.setStrokeColor(colors.HexColor("#B91C1C"))
    c.setLineWidth(3)
    c.rect(border_margin, border_margin,
           W - 2*border_margin, H - 2*border_margin, fill=0, stroke=1)

    # inner thin border
    c.setLineWidth(1)
    c.setStrokeColor(colors.HexColor("#FCA5A5"))
    inner = border_margin + 6
    c.rect(inner, inner, W - 2*inner, H - 2*inner, fill=0, stroke=1)

    # TOP RED BANNER
    banner_h = 90
    c.setFillColor(colors.HexColor("#B91C1C"))
    c.rect(inner, H - inner - banner_h, W - 2*inner, banner_h, fill=1, stroke=0)

    # ORG NAME
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(W/2, H - inner - 40, ORG_NAME.upper())
    c.setFont("Helvetica", 13)
    c.drawCentredString(W/2, H - inner - 62, ORG_SUBTITLE)

    # CERTIFICATE TITLE
    c.setFillColor(colors.HexColor("#7F1D1D"))
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(W/2, H - inner - banner_h - 80,
                        "CERTIFICATE OF APPRECIATION")

    line_y = H - inner - banner_h - 88
    c.setStrokeColor(colors.HexColor("#B91C1C"))
    c.setLineWidth(1.5)
    c.line(W/2 - 140, line_y, W/2 + 140, line_y)

    # INTRO TEXT
    c.setFillColor(colors.HexColor("#374151"))
    c.setFont("Helvetica", 12)
    c.drawCentredString(W/2, H - inner - banner_h - 108, "This is to certify that")

    # DONOR NAME
    c.setFillColor(colors.HexColor("#B91C1C"))
    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(W/2, H - inner - banner_h - 145, donor["name"])

    name_y = H - inner - banner_h - 150
    c.setStrokeColor(colors.HexColor("#FCA5A5"))
    c.setLineWidth(1)
    c.line(W/2 - 160, name_y, W/2 + 160, name_y)

    # APPRECIATION TEXT
    c.setFillColor(colors.HexColor("#374151"))
    c.setFont("Helvetica", 11.5)
    c.drawCentredString(W/2, H - inner - banner_h - 170,
                        "has generously donated blood and demonstrated an extraordinary act of humanity.")
    c.drawCentredString(W/2, H - inner - banner_h - 186,
                        "We express our heartfelt gratitude for this noble contribution that can save many precious lives.")

    # DONOR DETAILS TABLE
    detail_y = H - inner - banner_h - 215
    col1_x = W/2 - 230
    col2_x = W/2 - 20
    row_h = 24

    def detail_row(label, value, y):
        c.setFillColor(colors.HexColor("#6B7280"))
        c.setFont("Helvetica", 10)
        c.drawString(col1_x, y, label + ":")
        c.setFillColor(colors.HexColor("#111827"))
        c.setFont("Helvetica-Bold", 11)
        c.drawString(col1_x + 95, y, str(value))

    def detail_row_r(label, value, y):
        c.setFillColor(colors.HexColor("#6B7280"))
        c.setFont("Helvetica", 10)
        c.drawString(col2_x, y, label + ":")
        c.setFillColor(colors.HexColor("#111827"))
        c.setFont("Helvetica-Bold", 11)
        c.drawString(col2_x + 95, y, str(value))

    detail_row("Blood Group",    donor["blood_group"],                     detail_y)
    detail_row_r("Donation Date", donor["don_date"],                       detail_y)
    detail_row("Donation ID",    donor["don_id"],                          detail_y - row_h)
    detail_row_r("Units Donated", donor["units"] + " unit(s)",            detail_y - row_h)
    detail_row("Donor Age",      (donor["age"] + " years") if donor["age"] else "—",
                                                                           detail_y - 2*row_h)
    detail_row_r("Gender",       donor["gender"],                          detail_y - 2*row_h)

    # THANK YOU
    thanks_y = detail_y - 3*row_h - 10
    c.setFillColor(colors.HexColor("#B91C1C"))
    c.setFont("Helvetica-BoldOblique", 12)
    c.drawCentredString(W/2, thanks_y,
        '"Thank you for your noble act of donating blood and helping save lives."')

    # ── SIGNATURE + QR ─────────────────────────────────────────
    sig_y = inner + 30

    # Signature image — place signature.png in static/ folder to use it
    sig_img_path = os.path.join("static", "signature.png")
    if os.path.exists(sig_img_path):
        try:
            sig_img = ImageReader(sig_img_path)
            c.drawImage(sig_img, inner + 30, sig_y + 22,
                        width=190, height=48,
                        preserveAspectRatio=True, mask='auto')
        except Exception:
            pass  # fall back to plain line if image fails

    # Signature line
    c.setStrokeColor(colors.HexColor("#374151"))
    c.setLineWidth(1)
    c.line(inner + 30, sig_y + 20, inner + 220, sig_y + 20)

    # Labels
    c.setFillColor(colors.HexColor("#374151"))
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(inner + 125, sig_y + 7, "Authorised Signatory")
    c.setFont("Helvetica", 9)
    c.drawCentredString(inner + 125, sig_y - 4, ORG_NAME)

    # Issue date
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.HexColor("#6B7280"))
    c.drawCentredString(W/2, sig_y + 10,
        "Issued on: " + datetime.now().strftime("%d %B %Y"))

    # ── QR CODE — auto-detects live domain so verification always works ──
    base_url = APP_URL.rstrip("/")
    if "your-app.onrender.com" in base_url:
        # APP_URL env var not set — detect from live request
        try:
            from flask import request as flask_request
            base_url = flask_request.host_url.rstrip("/")
        except Exception:
            pass

    verify_url = f"{base_url}/verify/{donor['don_id']}"
    qr_buf = make_qr(verify_url)
    qr_img = ImageReader(qr_buf)
    qr_size = 75
    qr_x = W - inner - 45 - qr_size
    c.drawImage(qr_img, qr_x, sig_y - 8, qr_size, qr_size)
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#6B7280"))
    c.drawCentredString(qr_x + qr_size/2, sig_y - 16, "Scan to verify")

    # BOTTOM STRIP
    c.setFillColor(colors.HexColor("#B91C1C"))
    c.rect(inner, inner, W - 2*inner, 10, fill=1, stroke=0)

    c.save()
    buf.seek(0)
    return buf


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@app.route("/", methods=["GET", "POST"])
def index():
    error = None
    if request.method == "POST":
        mobile = request.form.get("mobile", "").strip()
        if not mobile:
            error = "Please enter your mobile number."
        elif not mobile.replace("+91", "").replace(" ", "").isdigit():
            error = "Please enter a valid mobile number."
        elif len(mobile.replace("+91", "").replace(" ", "")) < 10:
            error = "Mobile number must be at least 10 digits."
        else:
            return redirect(url_for("certificate", mobile=mobile.strip()))
    return render_template("index.html", error=error, org_name=ORG_NAME)


@app.route("/certificate/<path:mobile>")
def certificate(mobile):
    donor = find_donor(mobile)
    if donor is None:
        return render_template("error.html", mobile=mobile, org_name=ORG_NAME)
    # Store donor in session so download doesn't need a second Sheet lookup
    session["donor"] = donor
    return render_template("certificate.html", donor=donor, org_name=ORG_NAME)


@app.route("/download")
def download():
    # Try session first (fast, no Sheet lookup)
    donor = session.get("donor")

    # Fallback: re-lookup via query param
    if donor is None:
        mobile = request.args.get("mobile", "").strip()
        if mobile:
            donor = find_donor(mobile)

    if donor is None:
        return render_template("error.html",
                               mobile="unknown",
                               org_name=ORG_NAME), 404

    pdf_buf = generate_certificate_pdf(donor)
    filename = f"BloodDonation_Certificate_{donor['don_id']}.pdf"
    return send_file(
        pdf_buf,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


@app.route("/verify/<don_id>")
def verify(don_id):
    sheet = get_sheet()
    records = sheet.get_all_values()
    donor = None
    for row in records[1:]:
        if len(row) > COL_DON_ID and row[COL_DON_ID].strip() == don_id.strip():
            donor = {
                "name":        row[COL_NAME],
                "blood_group": row[COL_BLOOD_GROUP],
                "don_date":    row[COL_DON_DATE],
                "don_id":      row[COL_DON_ID],
                "units":       row[COL_UNITS],
            }
            break
    return render_template("verify.html", donor=donor, don_id=don_id, org_name=ORG_NAME)


@app.route("/health")
def health():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    app.run(debug=True)


# ─────────────────────────────────────────────
# SIGNATURE UPLOAD ROUTE
# ─────────────────────────────────────────────

@app.route("/admin/signature", methods=["GET", "POST"])
def upload_signature():
    """Simple admin page to upload the authorised signature image."""
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "chatra2024")
    msg = None
    success = False

    if request.method == "POST":
        # Check password
        pwd = request.form.get("password", "")
        if pwd != ADMIN_PASSWORD:
            msg = "Wrong password."
        elif "signature" not in request.files or request.files["signature"].filename == "":
            msg = "No file selected."
        else:
            f = request.files["signature"]
            allowed = {"png", "jpg", "jpeg"}
            ext = f.filename.rsplit(".", 1)[-1].lower()
            if ext not in allowed:
                msg = "Only PNG or JPG allowed."
            else:
                os.makedirs("static", exist_ok=True)
                # Always save as PNG for consistency
                from PIL import Image as PILImage
                img = PILImage.open(f).convert("RGBA")
                img.save(os.path.join("static", "signature.png"))
                msg = "Signature uploaded successfully! New certificates will include it."
                success = True

    has_sig = os.path.exists(os.path.join("static", "signature.png"))
    return render_template("admin_signature.html",
                           msg=msg, success=success,
                           has_sig=has_sig, org_name=ORG_NAME)
