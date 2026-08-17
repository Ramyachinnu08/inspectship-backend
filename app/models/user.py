from sqlalchemy import Column, Integer, String, DateTime, Enum, Boolean, Text
from sqlalchemy.sql import func
from ..core.database import Base
import enum


class UserRole(str, enum.Enum):
    admin = "admin"
    super_admin = "super_admin"
    inspector = "inspector"


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    name = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.inspector, nullable=False)
    phone = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # ─── 2FA (TOTP) ───
    totp_secret = Column(String, nullable=True)
    totp_enabled = Column(Boolean, default=False)
    totp_backup_codes = Column(Text, nullable=True)      # JSON list of hashed backup codes

    # ─── Passkeys (WebAuthn) ───
    passkey_credentials = Column(Text, nullable=True)    # JSON list of stored credentials