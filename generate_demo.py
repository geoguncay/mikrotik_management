"""Generate demo data for testing"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
import random

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from app.database import SessionLocal, Base, engine
from app.models import Host, RegistroTrafico


def populate_database():
    """Populate database with demo data"""
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    # Check if data already exists to avoid duplicates
    if db.query(Host).count() > 0:
        print("⚠️ Database already has registered clients.")
        print("If you want clean data, delete the 'db/traffic_counter.db' file and run this script again.")
        db.close()
        return

    print("📡 Creating demo clients...")
    # Using sample names and sectors for reference
    demo_clients = [
        Host(nombre="Juan Pérez - Sector Centro", ip_address="192.168.88.50", activo=True),
        Host(nombre="María Gómez - Turi", ip_address="192.168.88.51", activo=True),
        Host(nombre="Carlos Ruiz - Baños", ip_address="192.168.88.52", activo=False),
        Host(nombre="Cyber El Valle", ip_address="192.168.88.53", activo=True),
        Host(nombre="Torre Principal - Mgmt", ip_address="192.168.88.2", activo=True)
    ]
    
    db.add_all(demo_clients)
    db.commit()

    print("📊 Generating traffic history for the last 7 days...")
    
    # Simulate traffic for interesting dashboard charts later
    for client in demo_clients:
        if not client.activo:
            continue
            
        for days_ago in range(7, -1, -1):
            # Simulate daily consumption: Download 1GB to 15GB, Upload 100MB to 2GB
            download_bytes = random.randint(1_000_000_000, 15_000_000_000) 
            upload_bytes = random.randint(100_000_000, 2_000_000_000)
            
            # Simulated date
            record_date = datetime.utcnow() - timedelta(days=days_ago)
            
            record = RegistroTrafico(
                host_id=client.id,
                timestamp=record_date,
                bytes_descarga=download_bytes,
                bytes_subida=upload_bytes
            )
            db.add(record)
    
    db.commit()
    db.close()
    print("✅ Demo data injected successfully! Your application is ready for testing.")


if __name__ == "__main__":
    populate_database()
