from datetime import datetime
from enum import Enum

from sqlalchemy import Column, Integer,DateTime, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class MatchStatus(str, Enum):
    CREATED = "created"
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    DECLINED = "declined"
    CANCELLED = "cancelled"


class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)
    player1_id = Column(Integer, nullable=False)
    player2_id = Column(Integer, nullable=False)
    winner_id = Column(Integer, nullable=True)
    problem_id = Column(Integer, nullable=True)
    status = Column(SQLEnum(MatchStatus), nullable=False, default=MatchStatus.CREATED)
    start_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    end_time = Column(DateTime, nullable=True)
