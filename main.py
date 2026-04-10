import os
import asyncio
from datetime import datetime, timedelta
import routeros_api
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, create_engine, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# --- 1. DATABASE CONFIGURATION (SQLite) ---
# Using a local file. Remember to mount this on a USB in the RB5009!
SQLALCHEMY_DATABASE_URL = "sqlite:///./traffic_counter.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- 2. DATA MODELS (Tables) ---
class Host(Base):
    __tablename__ = "hosts"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True)
    ip_address = Column(String, unique=True, index=True) # The IP in the MikroTik
    activo = Column(Boolean, default=True)
    
    # Relationship with traffic records
    records = relationship("TrafficRecord", back_populates="host")

class TrafficRecord(Base):
    __tablename__ = "registros_trafico"
    id = Column(Integer, primary_key=True, index=True)
    host_id = Column(Integer, ForeignKey("hosts.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    bytes_descarga = Column(Integer, default=0) # Bytes Rx
    bytes_subida = Column(Integer, default=0)   # Bytes Tx

    host = relationship("Host", back_populates="records")

# Create the tables in the SQLite file if they don't exist
Base.metadata.create_all(bind=engine)

# --- 3. FASTAPI CONFIGURATION AND TEMPLATES ---
app = FastAPI(title="MikroTik Traffic Counter")
# Tell FastAPI where our HTML files are located
templates = Jinja2Templates(directory="templates")

# In-memory mutable configuration for the MikroTik connection.
CONFIG = {
    "MK_IP": os.getenv("MK_IP"),
    "MK_USER": os.getenv("MK_USER"),
    "MK_PASS": os.getenv("MK_PASS"),
    "INTERVALO_MINUTOS": int(os.getenv("INTERVALO_MINUTOS", "5")),
}

# --- 4. ROUTES (Endpoints) ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """
    Main route. Loads the base page structure (the menu and layout).
    """
    return templates.TemplateResponse(request, "base.html")

@app.get("/api/views/dashboard", response_class=HTMLResponse)
async def view_dashboard(request: Request):
    """
    HTMX Fragment: Returns only the HTML of the control panel.
    """
    db = SessionLocal()
    try:
        total_hosts = db.query(Host).count()
        active_hosts = db.query(Host).filter(Host.activo.is_(True)).count()
        inactive_hosts = total_hosts - active_hosts

        ago_24h = datetime.utcnow() - timedelta(hours=24)
        ago_7d = datetime.utcnow() - timedelta(days=7)

        total_24h_download = db.query(func.coalesce(func.sum(TrafficRecord.bytes_descarga), 0)).filter(
            TrafficRecord.timestamp >= ago_24h
        ).scalar() or 0
        total_24h_upload = db.query(func.coalesce(func.sum(TrafficRecord.bytes_subida), 0)).filter(
            TrafficRecord.timestamp >= ago_24h
        ).scalar() or 0

        total_7d_download = db.query(func.coalesce(func.sum(TrafficRecord.bytes_descarga), 0)).filter(
            TrafficRecord.timestamp >= ago_7d
        ).scalar() or 0
        total_7d_upload = db.query(func.coalesce(func.sum(TrafficRecord.bytes_subida), 0)).filter(
            TrafficRecord.timestamp >= ago_7d
        ).scalar() or 0

        total_traffic_expr = (func.sum(TrafficRecord.bytes_descarga) + func.sum(TrafficRecord.bytes_subida)).label("total")
        top_hosts_query = (
            db.query(
                Host.nombre,
                func.coalesce(func.sum(TrafficRecord.bytes_descarga), 0).label("descarga"),
                func.coalesce(func.sum(TrafficRecord.bytes_subida), 0).label("subida"),
                total_traffic_expr,
            )
            .join(TrafficRecord, TrafficRecord.host_id == Host.id)
            .filter(TrafficRecord.timestamp >= ago_7d)
            .group_by(Host.id)
            .order_by(total_traffic_expr.desc())
            .limit(5)
            .all()
        )

        top_hosts = [
            {
                "nombre": row.nombre,
                "descarga": int(row.descarga or 0),
                "subida": int(row.subida or 0),
                "total": int(row.total or 0),
            }
            for row in top_hosts_query
        ]
    finally:
        db.close()

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "total_hosts": total_hosts,
            "hosts_activos": active_hosts,
            "hosts_inactivos": inactive_hosts,
            "total_24h_descarga": total_24h_download,
            "total_24h_subida": total_24h_upload,
            "total_7d_descarga": total_7d_download,
            "total_7d_subida": total_7d_upload,
            "top_hosts": top_hosts,
        },
    )

@app.get("/api/views/clientes", response_class=HTMLResponse)
async def view_clients(request: Request):
    """
    HTMX Fragment: Returns the client table.
    """
    db = SessionLocal()
    # Get all hosts from the database
    clients_db = db.query(Host).all()
    db.close()
    
    # Pass the clients to the template to render them
    return templates.TemplateResponse(request, "clients.html", {"clientes": clients_db})

@app.get("/api/views/modal_add_config", response_class=HTMLResponse)
async def view_modal_add_config(request: Request):
    """
    Returns the empty modal form HTML.
    """
    return templates.TemplateResponse(request, "modals/modal_add_config.html")


@app.get("/api/views/configuracion", response_class=HTMLResponse)
async def view_config(request: Request):
    """HTMX Fragment to view and update RB connection configuration."""
    return templates.TemplateResponse(
        request,
        "config.html",
        {
            "mk_ip": CONFIG["MK_IP"],
            "mk_user": CONFIG["MK_USER"],
            "intervalo_minutos": CONFIG["INTERVALO_MINUTOS"],
            "message": None,
        },
    )


@app.post("/api/configuracion", response_class=HTMLResponse)
async def update_config(
    request: Request,
    mk_ip: str = Form(...),
    mk_user: str = Form(...),
    mk_pass: str = Form(""),
    intervalo_minutos: int = Form(...),
):
    """Updates the MikroTik connection configuration used by the collector in memory."""
    CONFIG["MK_IP"] = mk_ip.strip()
    CONFIG["MK_USER"] = mk_user.strip()
    if mk_pass.strip():
        CONFIG["MK_PASS"] = mk_pass
    CONFIG["INTERVALO_MINUTOS"] = max(1, min(intervalo_minutos, 1440))

    return templates.TemplateResponse(
        request,
        "config.html",
        {
            "mk_ip": CONFIG["MK_IP"],
            "mk_user": CONFIG["MK_USER"],
            "intervalo_minutos": CONFIG["INTERVALO_MINUTOS"],
            "message": "Configuración actualizada en memoria. Para persistirla, usa variables de entorno o un archivo de configuración.",
        },
    )

@app.post("/api/clientes", response_class=HTMLResponse)
async def add_client(
    request: Request,
    nombre: str = Form(...),
    ip_address: str = Form(...),
    activo: str = Form(None) # HTML checkboxes send "on" if checked, or None if not
):
    """
    Receives form data via HTMX, saves to SQLite, and returns the updated table.
    """
    # Convert the checkbox value to a real Python boolean
    is_active = True if activo == "on" else False
    
    db = SessionLocal()
    
    try:
        # Create the new database record
        new_host = Host(nombre=nombre, ip_address=ip_address, activo=is_active)
        db.add(new_host)
        db.commit()
    except SQLAlchemyError as e:
        # In a real case, we would handle the error here (e.g., if the IP already exists)
        db.rollback()
        print(f"Error saving: {e}")
    finally:
        # Query all clients, including the one we just added
        clients_db = db.query(Host).all()
        db.close()
    
    # HTMX TRICK: Return the complete 'clients.html' view.
    # HTMX will inject it into #main-content. Since #modal-container is
    # INSIDE clients.html, re-rendering everything makes the modal disappear magically.
    return templates.TemplateResponse(request, "clients.html", {"clientes": clients_db})

@app.delete("/api/clientes/{cliente_id}", response_class=HTMLResponse)
async def delete_client(request: Request, cliente_id: int):
    """
    Additional route for the red trash button in the table to work.
    """
    db = SessionLocal()
    client = db.query(Host).filter(Host.id == cliente_id).first()
    if client:
        db.delete(client)
        db.commit()
    
    clients_db = db.query(Host).all()
    db.close()
    
    return templates.TemplateResponse(request, "clients.html", {"clientes": clients_db})

# RAM dictionary to remember the last reading of each IP
# Format: {"192.168.88.50": {"rx": 1000500, "tx": 500200}}
last_readings = {}

async def collect_traffic():
    """
    This function runs in a loop in the background every X minutes.
    """
    while True:
        print(f"[{datetime.utcnow()}] Starting traffic collection...")
        db = SessionLocal()
        
        try:
            # 1. Get active clients from SQLite
            active_clients = db.query(Host).filter(Host.activo == True).all()
            
            if not active_clients:
                print("No active clients to monitor.")
                await asyncio.sleep(CONFIG["INTERVALO_MINUTOS"] * 60)
                continue

            # 2. Connect to MikroTik via API
            connection = routeros_api.RouterOsApiPool(
                CONFIG["MK_IP"],
                username=CONFIG["MK_USER"],
                password=CONFIG["MK_PASS"],
                plaintext_login=True,
            )
            api = connection.get_api()

            # 3. Read Simple Queues
            # We assume you limit/control your clients using Simple Queues and that the queue name
            # or target IP matches our record.
            list_queues = api.get_resource('/queue/simple')
            queues = list_queues.get()

            # 4. Process traffic
            for client in active_clients:
                # We look for the queue that belongs to this client's IP
                client_queue = next((q for q in queues if client.ip_address in q.get('target', '')), None)
                
                if client_queue:
                    # 'bytes' comes as a string: "BytesTx/BytesRx" (Upload/Download from the router's perspective)
                    bytes_str = client_queue.get('bytes', '0/0')
                    tx_str, rx_str = bytes_str.split('/')
                    current_tx, current_rx = int(tx_str), int(rx_str)

                    ip = client.ip_address
                    
                    # Calculate the Delta (actual consumption in this interval)
                    if ip in last_readings:
                        delta_tx = current_tx - last_readings[ip]['tx']
                        delta_rx = current_rx - last_readings[ip]['rx']
                        
                        # If delta is negative, it means the router restarted or counters reset
                        if delta_tx < 0 or delta_rx < 0:
                            delta_tx, delta_rx = current_tx, current_rx
                            
                        # Save the delta to SQLite
                        new_record = TrafficRecord(
                            host_id=client.id,
                            bytes_descarga=delta_rx,
                            bytes_subida=delta_tx
                        )
                        db.add(new_record)
                    
                    # Update RAM memory for the next iteration
                    last_readings[ip] = {'tx': current_tx, 'rx': current_rx}

            db.commit()
            connection.disconnect()
            print("Collection completed and saved to SQLite.")

        except (routeros_api.exceptions.RouterOsApiConnectionError, routeros_api.exceptions.RouterOsApiCommunicationError, SQLAlchemyError) as e:
            print(f"Error connecting to MikroTik: {e}")
            db.rollback()
        finally:
            db.close()

        # Sleep until the next cycle
        await asyncio.sleep(CONFIG["INTERVALO_MINUTOS"] * 60)

# --- FASTAPI STARTUP EVENT ---
@app.on_event("startup")
async def start_background_tasks():
    """
    Tells FastAPI to fire up the collection loop as soon as the server starts.
    """
    asyncio.create_task(collect_traffic())

# To run the server for local testing:
# uvicorn main:app --reload
