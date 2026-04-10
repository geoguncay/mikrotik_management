#!/bin/bash

# MikroTik Management Dashboard - Quick Start Script
# Este script configura el proyecto localmente de forma rápida

set -e  # Salir si hay error

echo "=========================================="
echo "MikroTik Management Dashboard - Setup"
echo "=========================================="
echo ""

# Detectar OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macOS"
    PYTHON_CMD="python3"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="Linux"
    PYTHON_CMD="python3"
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
    OS="Windows"
    PYTHON_CMD="python"
else
    OS="Unknown"
    PYTHON_CMD="python3"
fi

echo "✓ OS detectado: $OS"
echo ""

# Verificar Python
echo "Verificando Python..."
if ! command -v $PYTHON_CMD &> /dev/null; then
    echo "✗ Python no encontrado. Instala Python 3.11+ primero."
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
echo "✓ Python $PYTHON_VERSION encontrado"
echo ""

# Crear entorno virtual
echo "Creando entorno virtual..."
if [ ! -d ".venv" ]; then
    $PYTHON_CMD -m venv .venv
    echo "✓ Entorno virtual creado"
else
    echo "✓ Entorno virtual ya existe"
fi

# Activar entorno virtual
echo "Activando entorno virtual..."
if [[ "$OS" == "Windows" ]]; then
    source .venv/Scripts/activate
else
    source .venv/bin/activate
fi
echo "✓ Entorno activado"
echo ""

# Actualizar pip
echo "Actualizando pip..."
pip install --upgrade pip > /dev/null 2>&1
echo "✓ pip actualizado"
echo ""

# Instalar dependencias
echo "Instalando dependencias..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo "✓ Dependencias instaladas"
else
    echo "✗ requirements.txt no encontrado"
    exit 1
fi
echo ""

# Crear .env desde .env.example
echo "Configurando variables de entorno..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "✓ Archivo .env creado desde .env.example"
        echo ""
        echo "Por favor, edita .env con tus credenciales de MikroTik:"
        echo "  - MK_IP: IP del MikroTik"
        echo "  - MK_USER: Usuario API"
        echo "  - MK_PASS: Contraseña API"
        echo ""
        
        # Preguntar si lo quiere editar ahora
        read -p "¿Deseas editar .env ahora? (s/n): " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Ss]$ ]]; then
            if command -v nano &> /dev/null; then
                nano .env
            elif command -v vim &> /dev/null; then
                vim .env
            elif command -v code &> /dev/null; then
                code .env
            else
                echo "Abre .env en tu editor de texto favorito"
            fi
        fi
    else
        echo "✗ .env.example no encontrado"
        exit 1
    fi
else
    echo "✓ .env ya existe"
fi
echo ""

# Crear directorios necesarios
echo "Creando directorios..."
mkdir -p data db logs
echo "✓ Directorios creados"
echo ""

# Mostrar información final
echo "=========================================="
echo "✓ Setup completado exitosamente"
echo "=========================================="
echo ""
echo "Próximos pasos:"
echo ""
echo "1. Asegúrate de haber configurado .env con:"
echo "   - IP del MikroTik"
echo "   - Usuario y contraseña API"
echo ""
echo "2. Ejecuta la aplicación con:"
echo "   uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "3. Abre en tu navegador:"
echo "   http://localhost:8000"
echo ""
echo "Para más información, consulta README.md"
echo ""
