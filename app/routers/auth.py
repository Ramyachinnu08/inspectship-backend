from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..core.security import hash_password, verify_password, create_access_token, decode_token
from ..models.user import User, UserRole
from ..schemas.user import UserRegister, UserLogin, UserResponse, Token

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
        if hasattr(current_user, "totp_enabled"):
            current_user.totp_secret = secret
            current_user.totp_enabled = True
            db.commit()
        return {"success": True, "message": "Two-factor authentication enabled"}
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