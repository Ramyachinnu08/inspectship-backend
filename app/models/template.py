from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base

class Template(Base):
    __tablename__ = "templates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    version = Column(String, default="1.0")
    sections = Column(JSON, nullable=True)  # stores sections + questions as JSON
    created_at = Column(DateTime(timezone=True), server_default=func.now())