"""Database configuration and session management"""
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Database URL - use absolute path to ensure consistency across different execution contexts
# Get the project root (parent of backend folder)
PROJECT_ROOT = Path(__file__).parent.parent.parent
DB_FOLDER = PROJECT_ROOT / "db"
DB_FOLDER.mkdir(exist_ok=True)  # Ensure db folder exists
DB_PATH = DB_FOLDER / "traffic_counter.db"

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{DB_PATH}"
)

# Create engine and session factory
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base for all models
Base = declarative_base()

def get_db():
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
