from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.sql import func
from ..core.database import Base

class Inspection(Base):
    __tablename__ = "inspections"
    
    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False)
    answers = Column(JSON, nullable=True)  # {question_id: {answer, comment, photos}}
    master_name = Column(String, nullable=True)
    master_email = Column(String, nullable=True)
    master_signature_url = Column(String, nullable=True)
    inspector_signature_url = Column(String, nullable=True)
    completion_date = Column(DateTime, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())