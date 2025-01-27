from sqlalchemy import Column, Integer, String

from core.database import Base


class FunctionModel(Base):
    __tablename__ = "functions"
    __table_args__ = {"schema": "function"}
    __versioned__ = {}  # Enable version tracking

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)
