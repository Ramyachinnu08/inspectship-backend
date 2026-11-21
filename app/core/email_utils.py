"""
Email sending utility.

Configure by setting these environment variables (or edit the defaults below):
  SMTP_HOST      (default smtp.gmail.com)
  SMTP_PORT      (default 587)
  SMTP_USER      your gmail address, e.g. yourname@gmail.com
  SMTP_PASSWORD  your 16-char Gmail App Password (no spaces)
  SMTP_FROM      the "from" address (defaults to SMTP_USER)

If SMTP_USER / SMTP_PASSWORD are not set, send_email() does nothing and
returns False (so the app still works — the reset link is returned in the
API response for testing).
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# ─── Configuration ──────────────────────────────────────
# You can hard-code these here instead of env vars if you prefer:
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")          # <-- your gmail address
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")  # <-- your 16-char app password
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER or "no-reply@inspectship.com")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")          # <-- where submitted reports are sent


def is_configured() -> bool:
    return bool(SMTP_USER and SMTP_PASSWORD)


def send_email(to_email, subject: str, html_body: str, attachments=None) -> bool:
    """Send an HTML email to one address or a list of addresses.
    attachments: optional list of (filename, bytes, mime_subtype) e.g. ("report.pdf", b"...", "pdf").
    Returns True if sent, False if not configured or failed."""
    if not is_configured():
        print("[email] SMTP not configured - skipping:", subject)
        return False
    recipients = [to_email] if isinstance(to_email, str) else [e for e in (to_email or []) if e]
    recipients = [r.strip() for r in recipients if r and r.strip()]
    if not recipients:
        return False
    try:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(html_body, "html"))
        for (fname, data, subtype) in (attachments or []):
            part = MIMEBase("application", subtype or "octet-stream")
            part.set_payload(data)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="{fname}"')
            msg.attach(part)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, recipients, msg.as_string())
        return True
    except Exception as e:
        print(f"[email] send failed: {e}")
        return False


def _wrap(title: str, body_html: str) -> str:
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;color:#111;">
      <div style="background:#1A2A5E;padding:20px;text-align:center;">
        <span style="color:#FF6B00;font-weight:800;font-size:18px;letter-spacing:1px;">RIGHTKNOTS</span>
      </div>
      <div style="padding:28px 24px;">
        <h2 style="margin:0 0 12px;font-size:20px;">{title}</h2>
        {body_html}
      </div>
      <div style="background:#F3F4F6;padding:16px;text-align:center;font-size:12px;color:#9CA3AF;">
        © 2026 RightKnots Shipping. All rights reserved.
      </div>
    </div>
    """


def _row(label, value):
    return (f'<tr><td style="padding:6px 10px;color:#6B7280;font-size:13px;">{label}</td>'
            f'<td style="padding:6px 10px;font-weight:700;font-size:13px;">{value or "-"}</td></tr>')


def assignment_created_html(inspector_name, vessel_name, imo, port, due_date, template_name, notes) -> str:
    rows = "".join([
        _row("Vessel", f"{vessel_name} ({imo})" if imo else vessel_name),
        _row("Port", port),
        _row("Due date", due_date),
        _row("Template", template_name),
        _row("Notes", notes),
    ])
    body = f"""
        <p style="font-size:14px;color:#374151;line-height:1.6;">Dear {inspector_name or "Inspector"},</p>
        <p style="font-size:14px;color:#374151;line-height:1.6;">
          A new inspection assignment has been created for you. Please open the RightKnots app to start.
        </p>
        <table style="border-collapse:collapse;width:100%;margin:16px 0;border:1px solid #E5E7EB;">{rows}</table>
    """
    return _wrap("New inspection assignment", body)


def report_submitted_html(vessel_name, imo, port, inspector_name, inspection_date, findings, master_name) -> str:
    rows = "".join([
        _row("Vessel", f"{vessel_name} ({imo})" if imo else vessel_name),
        _row("Port of inspection", port),
        _row("Inspector", inspector_name),
        _row("Date of inspection", inspection_date),
        _row("Master", master_name),
        _row("Findings raised", findings),
    ])
    body = f"""
        <p style="font-size:14px;color:#374151;line-height:1.6;">
          The inspection for <b>{vessel_name}</b> has been submitted. The full inspection report is attached as a PDF.
        </p>
        <table style="border-collapse:collapse;width:100%;margin:16px 0;border:1px solid #E5E7EB;">{rows}</table>
        <p style="font-size:12px;color:#6B7280;">Confidential - for the addressees only.</p>
    """
    return _wrap("Inspection report submitted", body)


def reset_password_html(reset_link: str, expires_hours: int = 1) -> str:
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;color:#111;">
      <div style="background:#1A2A5E;padding:20px;text-align:center;">
        <span style="color:#FF6B00;font-weight:800;font-size:18px;letter-spacing:1px;">RIGHTKNOT</span>
      </div>
      <div style="padding:28px 24px;">
        <h2 style="margin:0 0 12px;font-size:20px;">Reset your password</h2>
        <p style="font-size:14px;color:#374151;line-height:1.6;">
          We received a request to reset the password for your RightKnot inspector account.
        </p>
        <div style="text-align:center;margin:24px 0;">
          <a href="{reset_link}" style="background:#FF6B00;color:#fff;text-decoration:none;
             padding:12px 28px;border-radius:8px;font-weight:700;font-size:15px;display:inline-block;">
            Reset your password
          </a>
        </div>
        <p style="font-size:13px;color:#6B7280;line-height:1.6;">
          This link expires in {expires_hours} hour(s). If you didn't make this request,
          you can safely ignore this email.
        </p>
      </div>
      <div style="background:#F3F4F6;padding:16px;text-align:center;font-size:12px;color:#9CA3AF;">
        © 2026 RightKnot Shipping. All rights reserved.
      </div>
    </div>
    """