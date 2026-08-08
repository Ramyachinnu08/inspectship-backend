from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base
import enum

class AssignmentStatus(str, enum.Enum):
    upcoming = "upcoming"
    in_progress = "in_progress"
    submitted = "submitted"
    overdue = "overdue"

class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, index=True)
    vessel_id = Column(Integer, ForeignKey("vessels.id"), nullable=False)
    template_id = Column(Integer, ForeignKey("templates.id"), nullable=True)
    inspector_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    due_date = Column(DateTime, nullable=True)
    port = Column(String, nullable=True)
    scope = Column(String, default="standard")
    status = Column(Enum(AssignmentStatus), default=AssignmentStatus.upcoming)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())