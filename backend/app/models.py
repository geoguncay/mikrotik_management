"""Database models for traffic monitoring"""
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .database import Base


class Host(Base):
    """Host/Client model for tracking traffic"""
    __tablename__ = "hosts"
    
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True)  # Client name
    ip_address = Column(String, unique=True, index=True)  # IP in MikroTik
    activo = Column(Boolean, default=True)  # Active status
    
    # Relationship with traffic records
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
