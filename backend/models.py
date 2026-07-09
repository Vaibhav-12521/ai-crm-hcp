from datetime import datetime, date

from sqlalchemy import Column, Integer, String, Text, Date, DateTime

from database import Base


class HCP(Base):
    __tablename__ = "hcps"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    specialty = Column(String(200), nullable=True)
    location = Column(String(200), nullable=True)


class Interaction(Base):
    __tablename__ = "interactions"

    id = Column(Integer, primary_key=True, index=True)
    hcp_name = Column(String(200), nullable=False, index=True)
    date = Column(Date, nullable=False, default=date.today)
    time = Column(String(20), nullable=True)
    location = Column(String(200), nullable=True)
    interaction_type = Column(String(100), nullable=True)
    attendees = Column(String(400), nullable=True)
    notes = Column(Text, nullable=True)
    materials_shared = Column(String(400), nullable=True)
    samples_distributed = Column(String(400), nullable=True)
    outcome = Column(Text, nullable=True)
    follow_up_actions = Column(Text, nullable=True)

    summary = Column(Text, nullable=True)
    sentiment = Column(String(50), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
