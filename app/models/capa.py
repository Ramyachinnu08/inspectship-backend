from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from ..core.database import Base

class CAPA(Base):
    __tablename__ = "capas"
    
    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("reports.id"), nullable=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=True)
    question_text = Column(Text, nullable=True)
    finding = Column(Text, nullable=False)
    corrective_action = Column(Text, nullable=True)
    status = Column(String, default="open")  # open, in_progress, closed
    due_date = Column(DateTime, nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())