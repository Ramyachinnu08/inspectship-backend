from sqlalchemy import Column, Integer, String, DateTime, Enum
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