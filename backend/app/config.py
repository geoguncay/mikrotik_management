"""Configuration management for MikroTik connections"""
import os

# Mutable configuration in memory for MikroTik connections
CONFIG = {
    "MK_IP": os.getenv("MK_IP", "172.17.0.1"),
    "MK_USER": os.getenv("MK_USER", "api_user"),
    "MK_PASS": os.getenv("MK_PASS", "secure_password_here"),
    "INTERVALO_MINUTOS": int(os.getenv("INTERVALO_MINUTOS", "5")),  # Interval in minutes
}

def get_config():
    """Get current configuration"""
    return CONFIG

def update_config(mk_ip: str = None, mk_user: str = None, mk_pass: str = None, intervalo_minutos: int = None):
    """Update configuration in memory"""
    if mk_ip is not None:
        CONFIG["MK_IP"] = mk_ip.strip()
    if mk_user is not None:
        CONFIG["MK_USER"] = mk_user.strip()
    if mk_pass is not None and mk_pass.strip():
        CONFIG["MK_PASS"] = mk_pass
    if intervalo_minutos is not None:
        CONFIG["INTERVALO_MINUTOS"] = max(1, min(intervalo_minutos, 1440))
    return CONFIG
