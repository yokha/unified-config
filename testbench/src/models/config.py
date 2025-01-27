from sqlalchemy import JSON, Column, DateTime, Integer, String, func
from sqlalchemy_continuum import make_versioned

from core.database import Base

make_versioned(user_cls=None)


class ConfigModel(Base):
    __tablename__ = "configurations"
    __table_args__ = {"schema": "configuration"}  # Use "configuration" schema
    __versioned__ = {}  # Enable version tracking

    section = Column(String, primary_key=True)
    key = Column(String, primary_key=True)
    value = Column(JSON)


class ConfigHistoryModel(Base):
    """Stores changes in configuration"""

    __tablename__ = "config_history"
    __table_args__ = {"schema": "configuration"}  # Use "configuration" schema

    id = Column(String, primary_key=True)
    section = Column(String, nullable=False)
    key = Column(String, nullable=True)  # Can be null if entire section is updated
    new_value = Column(JSON, nullable=False)
    timestamp = Column(DateTime, default=func.now(), nullable=False)
    updated_by = Column(String, nullable=False)
