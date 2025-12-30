"""SQLAlchemy Base class for model definitions."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models.

    Define your models by inheriting from this class:

        from app.db import Base
        from sqlalchemy import Column, Integer, String

        class User(Base):
            __tablename__ = "users"

            id = Column(Integer, primary_key=True)
            email = Column(String, unique=True, nullable=False)
            name = Column(String)
    """

    pass

