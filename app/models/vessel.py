from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base

class Vessel(Base):
    __tablename__ = "vessels"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    imo = Column(String, unique=True, index=True, nullable=False)
    vessel_type = Column(String, nullable=True)
    flag = Column(String, nullable=True)
    operator = Column(String, nullable=True)
    build_year = Column(Integer, nullable=True)
    fleet_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())