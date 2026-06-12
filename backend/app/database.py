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

def run_migrations():
    """Migrate the SQLite schema by adding columns if they do not exist"""
    from pathlib import Path
    import sqlite3
    db_path = Path(__file__).parent.parent.parent / "db" / "traffic_counter.db"
    db_paths = [db_path, Path(__file__).parent.parent.parent / "traffic_counter.db"]
    
    for path in db_paths:
        if path.exists():
            try:
                conn = sqlite3.connect(path)
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(hosts)")
                columns = [info[1] for info in cursor.fetchall()]
                if columns and "router_id" not in columns:
                    print(f"Migrating database ({path.name}): adding router_id column to hosts table...")
                    cursor.execute("ALTER TABLE hosts ADD COLUMN router_id INTEGER REFERENCES routers(id)")
                    conn.commit()
                conn.close()
            except Exception as e:
                print(f"Migration error for {path.name}: {e}")

# Run migrations automatically
try:
    run_migrations()
except Exception as e:
    print(f"Migration execution error: {e}")

def get_db():
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
