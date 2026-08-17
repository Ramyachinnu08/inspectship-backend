from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..core.security import hash_password, verify_password, create_access_token, decode_token
from ..models.user import User, UserRole
from ..schemas.user import UserRegister, UserLogin, UserResponse, Token
import secrets
import json
from datetime import datetime, timedelta
try:
    from ..core.email_utils import send_email, reset_password_html, is_configured
except Exception:
    # email utils optional
    def send_email(*a, **k): return False
    def reset_password_html(link, expires_hours=1): return ""
    def is_configured(): return False

router = APIRouter(prefix="/auth", tags=["Authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

# ─── Register ───────────────────────────────────────────
@router.post("/register", response_model=UserResponse)
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        name=user_data.name,
        role=UserRole(user_data.role),
        phone=user_data.phone,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

# ─── Login (JSON body - for Flutter/React apps) ─────────
@router.post("/login", response_model=Token)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user,
    }

# ─── Login form (for Swagger Authorize button) ──────────
@router.post("/token", response_model=Token)
def login_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user,
    }

# ─── Get current user (protected route) ─────────────────
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user

# ─── Change Password ────────────────────────────────────
@router.post("/change-password")
def change_password(
    payload: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    old_password = payload.get("old_password", "")
    new_password = payload.get("new_password", "")

    if not verify_password(old_password, current_user.hashed_password):
        return {"success": False, "message": "Current password is incorrect"}

    if len(new_password) < 6:
        return {"success": False, "message": "New password must be at least 6 characters"}

    current_user.hashed_password = hash_password(new_password)
    db.commit()
    return {"success": True, "message": "Password changed successfully"}

# ─── TOTP (Authenticator 2FA) ───────────────────────────
# Requires: pip install pyotp qrcode
@router.post("/totp/setup")
def totp_setup(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a TOTP secret + otpauth URI for the user to scan."""
    try:
        import pyotp
    except ImportError:
        return {"success": False, "message": "TOTP not available. Install pyotp on the server."}

    secret = pyotp.random_base32()
    # store secret temporarily on the user (needs a totp_secret column; falls back to phone field note)
    # We store on user.totp_secret if the column exists, else return without persisting.
    if hasattr(current_user, "totp_secret"):
        current_user.totp_secret = secret
        current_user.totp_enabled = False
        db.commit()

    uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=current_user.email, issuer_name="InspectShip"
    )
    return {"success": True, "data": {"secret": secret, "otpauth_uri": uri}}

@router.post("/totp/verify")
def totp_verify(
    payload: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify the 6-digit code and enable TOTP."""
    try:
        import pyotp
    except ImportError:
        return {"success": False, "message": "TOTP not available. Install pyotp on the server."}

    code = str(payload.get("code", ""))
    secret = payload.get("secret") or (getattr(current_user, "totp_secret", None))
    if not secret:
        return {"success": False, "message": "No TOTP secret found. Run setup first."}

    totp = pyotp.TOTP(secret)
    if totp.verify(code, valid_window=1):
        backup_codes = []
        if hasattr(current_user, "totp_enabled"):
            current_user.totp_secret = secret
            current_user.totp_enabled = True
            # generate 8 backup codes, store hashed, return plaintext once
            plain_codes = []
            hashed_codes = []
            for _ in range(8):
                code_plain = f"{secrets.randbelow(10**4):04d}-{secrets.randbelow(10**4):04d}"
                plain_codes.append(code_plain)
                hashed_codes.append(hash_password(code_plain))
            current_user.totp_backup_codes = json.dumps(hashed_codes)
            backup_codes = plain_codes
            db.commit()
        return {"success": True, "message": "Two-factor authentication enabled", "backup_codes": backup_codes}
    return {"success": False, "message": "Invalid code. Try again."}

@router.post("/totp/disable")
def totp_disable(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if hasattr(current_user, "totp_enabled"):
        current_user.totp_enabled = False
        current_user.totp_secret = None
        db.commit()
    return {"success": True, "message": "Two-factor authentication disabled"}


@router.post("/totp/backup-codes/regenerate")
def regenerate_backup_codes(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Generate a fresh set of 8 backup codes (invalidates old ones)."""
    if not getattr(current_user, "totp_enabled", False):
        return {"success": False, "message": "Enable 2FA first"}
    plain_codes = []
    hashed_codes = []
    for _ in range(8):
        code_plain = f"{secrets.randbelow(10**4):04d}-{secrets.randbelow(10**4):04d}"
        plain_codes.append(code_plain)
        hashed_codes.append(hash_password(code_plain))
    current_user.totp_backup_codes = json.dumps(hashed_codes)
    db.commit()
    return {"success": True, "backup_codes": plain_codes}


@router.post("/totp/backup-codes/verify")
def verify_backup_code(payload: dict = Body(...), db: Session = Depends(get_db)):
    """Log in using a backup code (when authenticator is unavailable)."""
    email = (payload.get("email") or "").strip().lower()
    code = (payload.get("code") or "").strip()
    user = db.query(User).filter(User.email == email).first()
    if not user or not getattr(user, "totp_backup_codes", None):
        return {"success": False, "message": "Invalid code"}
    try:
        hashed_codes = json.loads(user.totp_backup_codes)
    except Exception:
        hashed_codes = []
    for i, h in enumerate(hashed_codes):
        if verify_password(code, h):
            # consume the code (one-time use)
            hashed_codes.pop(i)
            user.totp_backup_codes = json.dumps(hashed_codes)
            db.commit()
            token = create_access_token({"sub": str(user.id), "role": user.role.value if hasattr(user.role, "value") else str(user.role)})
            return {"success": True, "access_token": token, "token_type": "bearer",
                    "remaining_codes": len(hashed_codes),
                    "user": {"id": user.id, "email": user.email, "name": user.name,
                             "role": user.role.value if hasattr(user.role, "value") else str(user.role)}}
    return {"success": False, "message": "Invalid backup code"}


# ─── Passkeys (WebAuthn) ───
@router.post("/passkeys/save")
def save_passkey(payload: dict = Body(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Store a registered passkey credential for this user."""
    cred = payload.get("credential")
    if not cred:
        return {"success": False, "message": "No credential provided"}
    try:
        existing = json.loads(current_user.passkey_credentials) if current_user.passkey_credentials else []
    except Exception:
        existing = []
    existing.append({"id": cred.get("id"), "name": payload.get("name", "Passkey"), "created": datetime.utcnow().isoformat()})
    current_user.passkey_credentials = json.dumps(existing)
    db.commit()
    return {"success": True, "message": "Passkey saved", "count": len(existing)}


@router.get("/passkeys/list")
def list_passkeys(current_user: User = Depends(get_current_user)):
    """List this user's registered passkeys."""
    try:
        existing = json.loads(current_user.passkey_credentials) if current_user.passkey_credentials else []
    except Exception:
        existing = []
    return {"success": True, "passkeys": existing}


@router.post("/passkeys/verify")
def verify_passkey(payload: dict = Body(...), db: Session = Depends(get_db)):
    """Log in with a passkey: match the credential id to a stored user."""
    cred_id = payload.get("credential_id")
    if not cred_id:
        return {"success": False, "message": "No credential id"}
    users = db.query(User).filter(User.passkey_credentials.isnot(None)).all()
    for user in users:
        try:
            creds = json.loads(user.passkey_credentials)
        except Exception:
            creds = []
        if any(cr.get("id") == cred_id for cr in creds):
            token = create_access_token({"sub": str(user.id), "role": user.role.value if hasattr(user.role, "value") else str(user.role)})
            return {"success": True, "access_token": token, "token_type": "bearer",
                    "user": {"id": user.id, "email": user.email, "name": user.name,
                             "role": user.role.value if hasattr(user.role, "value") else str(user.role)}}
    return {"success": False, "message": "Passkey not recognized"}


# ─── Password Reset (Forgot Password) ───────────────────
# In-memory token store: token -> {email, expires}. Resets on server restart.
_reset_tokens = {}

# Where the reset page lives (adjust to your admin/inspector reset URL)
RESET_BASE_URL = "http://localhost:5173/reset-password"

@router.post("/forgot-password")
def forgot_password(payload: dict = Body(...), db: Session = Depends(get_db)):
    email = (payload.get("email") or "").strip().lower()
    if not email:
        return {"success": False, "message": "Email is required"}

    user = db.query(User).filter(User.email == email).first()
    # For security, respond success even if the email isn't found
    if not user:
        return {"success": True, "message": "If that email exists, a reset link has been sent."}

    # generate token + store with 1-hour expiry
    token = secrets.token_urlsafe(32)
    _reset_tokens[token] = {
        "email": email,
        "expires": datetime.utcnow() + timedelta(hours=1),
    }
    reset_link = f"{RESET_BASE_URL}?token={token}"

    # try to send the email
    sent = send_email(email, "Reset your Sea Secure password", reset_password_html(reset_link, 1))

    result = {"success": True, "message": "Reset link sent to your email."}
    if not sent:
        # email not configured — return the link so it can still be used/tested
        result["message"] = "Email not configured. Use the reset link below."
        result["reset_link"] = reset_link
    return result


@router.post("/reset-password")
def reset_password(payload: dict = Body(...), db: Session = Depends(get_db)):
    token = payload.get("token") or ""
    new_password = payload.get("new_password") or ""

    entry = _reset_tokens.get(token)
    if not entry:
        return {"success": False, "message": "Invalid or expired reset link"}
    if datetime.utcnow() > entry["expires"]:
        _reset_tokens.pop(token, None)
        return {"success": False, "message": "Reset link has expired. Request a new one."}
    if len(new_password) < 6:
        return {"success": False, "message": "Password must be at least 6 characters"}

    user = db.query(User).filter(User.email == entry["email"]).first()
    if not user:
        return {"success": False, "message": "Account not found"}

    user.hashed_password = hash_password(new_password)
    db.commit()
    _reset_tokens.pop(token, None)  # one-time use
    return {"success": True, "message": "Password reset successfully. You can now sign in."}