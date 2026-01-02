"""Database models.

Define your SQLAlchemy models here. Example:

    from app.db import Base
    from sqlalchemy import Column, Integer, String, DateTime
    from datetime import datetime

    class Item(Base):
        __tablename__ = "items"

        id = Column(Integer, primary_key=True)
        name = Column(String, nullable=False)
        description = Column(String)
        created_at = Column(DateTime, default=datetime.utcnow)

Import all models here to ensure they're registered with Base.metadata.
"""

# Import models here so they're registered with Base.metadata
# Example:
# from app.db.models.item import Item

__all__: list[str] = []
