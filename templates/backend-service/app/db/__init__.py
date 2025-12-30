"""Database module.

This module provides optional SQLAlchemy database support.
Enable via features.database in runtm.yaml.

Usage:
    from app.db import get_db, Base

    # In your models:
    class MyModel(Base):
        __tablename__ = "my_table"
        id = Column(Integer, primary_key=True)

    # In your routes:
    @router.get("/items")
    def get_items(db: Session = Depends(get_db)):
        return db.query(MyModel).all()
"""

from app.db.base import Base
from app.db.session import get_db, get_engine, get_session_factory

# Import models module to register all models with Base.metadata
# This is imported last to avoid circular imports
from app.db import models  # noqa: F401

__all__ = ["Base", "get_db", "get_engine", "get_session_factory", "models"]

