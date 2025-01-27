""" Db models"""
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, JSON, DateTime, func


Base = declarative_base()


class ConfigModel(Base):
    """Stores configurations"""

    __tablename__ = "configurations"
    __table_args__ = {"schema": "configuration"}  # Use "configuration" schema

    section = Column(String, primary_key=True)
    key = Column(String, primary_key=True)
    value = Column(JSON)


class ConfigHistoryModel(Base):
    """Stores changes in configuration"""

    __tablename__ = "config_history"
    __table_args__ = {"schema": "configuration"}  # Use "configuration" schema

    id = Column(String, primary_key=True)  # Use UUID
    section = Column(String, nullable=False)
    key = Column(String, nullable=True)  # Can be null if entire section is updated
    new_value = Column(JSON, nullable=False)
    timestamp = Column(
        DateTime, default=func.now(), nullable=False  # pylint: disable=not-callable
    )
    updated_by = Column(String, nullable=False)
