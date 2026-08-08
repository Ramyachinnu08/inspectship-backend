from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from ..core.database import Base

class CALibrary(Base):
    __tablename__ = "ca_library"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=True)
    severity = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())