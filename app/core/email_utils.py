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

# ─── Configuration ──────────────────────────────────────
# You can hard-code these here instead of env vars if you prefer:
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")          # <-- your gmail address
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")  # <-- your 16-char app password
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER or "no-reply@inspectship.com")


def is_configured() -> bool:
    return bool(SMTP_USER and SMTP_PASSWORD)


def send_email(to_email: str, subject: str, html_body: str) -> bool:
    """Send an HTML email. Returns True if sent, False if not configured or failed."""
    if not is_configured():
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [to_email], msg.as_string())
        return True
    except Exception as e:
        print(f"[email] send failed: {e}")
        return False


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