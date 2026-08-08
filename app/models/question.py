from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.sql import func
from ..core.database import Base

class QuestionBank(Base):
    __tablename__ = "question_bank"
    
    id = Column(Integer, primary_key=True, index=True)
    question = Column(Text, nullable=False)
    sub_number = Column(String, nullable=True)
    category = Column(String, nullable=True)
    sub_area = Column(String, nullable=True)
    severity = Column(String, nullable=True)
    type = Column(String, nullable=True)
    evidence_required = Column(Boolean, default=False)
    guide_to_inspection = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())