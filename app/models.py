from sqlalchemy import Column, Integer, String, DateTime, Enum
from sqlalchemy.sql import func
from app.database import Base
import enum


class StatusEnum(str, enum.Enum):
    new = "new"
    assigned = "assigned"
    in_progress = "in_progress"
    done = "done"
    canceled = "canceled"


class RoleEnum(str, enum.Enum):
    dispatcher = "dispatcher"
    master = "master"


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(RoleEnum), nullable=False)


class Request(Base):
    __tablename__ = "requests"
    id = Column(Integer, primary_key=True, index=True)
    clientName = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    address = Column(String, nullable=False)
    problemText = Column(String, nullable=False)
    status = Column(Enum(StatusEnum), default=StatusEnum.new, nullable=False)
    assignedTo = Column(Integer, nullable=True)
    createdAt = Column(DateTime, server_default=func.now())
    updatedAt = Column(DateTime, server_default=func.now(), onupdate=func.now())
