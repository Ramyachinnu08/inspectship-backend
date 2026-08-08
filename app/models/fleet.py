from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from ..core.database import Base

class Fleet(Base):
    __tablename__ = "fleets"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())