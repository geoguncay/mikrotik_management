"""Database models for traffic monitoring"""
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .database import Base


class Router(Base):
    """RouterBoard model for connecting to multiple MikroTiks"""
    __tablename__ = "routers"
    
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True)  # Alias (e.g. WISP Router 1)
    ip_address = Column(String, unique=True, index=True)  # Router IP
    usuario = Column(String)  # API Username
    password = Column(String)  # API Password
    intervalo_minutos = Column(Integer, default=5)  # Interval for data collection
    activo = Column(Boolean, default=True)  # Active monitoring status

    hosts = relationship("Host", back_populates="router", cascade="all, delete-orphan")


class Host(Base):
    """Host/Client model for tracking traffic"""
    __tablename__ = "hosts"
    
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True)  # Client name
    ip_address = Column(String, unique=True, index=True)  # IP in MikroTik
    activo = Column(Boolean, default=True)  # Active status
    router_id = Column(Integer, ForeignKey("routers.id"), nullable=True)  # Associated router
    
    # Relationships
    router = relationship("Router", back_populates="hosts")
    registros = relationship("RegistroTrafico", back_populates="host", cascade="all, delete-orphan")


class RegistroTrafico(Base):
    """Traffic record model"""
    __tablename__ = "registros_trafico"
    
    id = Column(Integer, primary_key=True, index=True)
    host_id = Column(Integer, ForeignKey("hosts.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    bytes_descarga = Column(Integer, default=0)  # Bytes Rx
    bytes_subida = Column(Integer, default=0)    # Bytes Tx
    
    host = relationship("Host", back_populates="registros")
