from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.sql import func
from ..core.database import Base

class Profile(Base):
    __tablename__ = "profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    kind = Column(String, nullable=False)  # randomness, scoring, ai, report
    name = Column(String, nullable=False)
    data = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())