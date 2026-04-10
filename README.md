# MikroTik Management Dashboard

Una aplicación web moderna para monitorear y gestionar el tráfico de red en dispositivos MikroTik RouterOS. Permite visualizar el consumo de ancho de banda en tiempo real, administrar clientes y listar equipos configurados.

## 📋 Características

- 🖥️ **Dashboard interactivo** - Visualización en tiempo real del consumo de red
- 📊 **Gráficos dinámicos** - Estadísticas de tráfico por hora, día, semana y mes
- 👥 **Gestión de clientes** - Agregar, editar y eliminar dispositivos monitoreados
- 📝 **Listas de direcciones** - Ver y administrar listas de firewall de MikroTik
- 🔄 **Actualizaciones en vivo** - Datos sincronizados automáticamente cada 5 segundos
- 🎯 **Interfaz responsiva** - Funciona en desktop, tablet y dispositivos móviles
- 🐳 **Docker ready** - Fácil despliegue con Docker y Docker Compose
- 🔌 **Conexión API** - Integración directa con RouterOS API

## 🚀 Inicio Rápido

### Con Docker (Recomendado)

```bash
# Clonar el repositorio
git clone https://github.com/geoguncay/mikrotik_management.git
cd mikrotik_management

# Crear archivo .env
cat > .env << EOF
MK_IP=192.168.1.1
MK_USER=api_user
MK_PASS=tu_contraseña_api
INTERVALO_MINUTOS=5
EOF

# Ejecutar con Docker Compose
docker-compose up -d

# Acceder a la aplicación
# http://localhost:8000
```

### Localmente (Desarrollo)

```bash
# Requisitos previos
# - Python 3.11+
# - pip

# Clonar el repositorio
git clone https://github.com/geoguncay/mikrotik_management.git
cd mikrotik_management

# Crear entorno virtual
python -m venv .venv

# Activar entorno virtual
# En Linux/macOS:
source .venv/bin/activate

# En Windows:
.venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Crear archivo .env (opcional)
cat > .env << EOF
MK_IP=192.168.1.1
MK_USER=api_user
MK_PASS=tu_contraseña_api
INTERVALO_MINUTOS=5
EOF

# Ejecutar la aplicación
python main.py

# O con uvicorn directamente:
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

# Acceder a la aplicación
# http://localhost:8000
```

## 📋 Requisitos Previos

### General
- Docker y Docker Compose (para Docker), O
- Python 3.11 o superior (para desarrollo local)
- Acceso a un dispositivo MikroTik con RouterOS

### MikroTik RouterOS
1. **Crear un usuario API con permisos necesarios:**
   ```
   /user add name=api_user password=contraseña group=full
   /ip service enable api
   /ip service set api port=8728
   ```

2. **Configurar las listas de direcciones en firewall:**
   ```
   /ip firewall address-list add list=nombre_lista address=192.168.1.0/24
   ```

## ⚙️ Configuración

### Variables de Entorno

Establece las siguientes variables en un archivo `.env`:

```env
# Dirección IP o hostname del MikroTik
MK_IP=192.168.1.1

# Usuario API configurado en el RouterOS
MK_USER=api_user

# Contraseña del usuario API
MK_PASS=tu_contraseña_segura

# Intervalo de recolección de datos en minutos (1-1440)
INTERVALO_MINUTOS=5

# Para Docker: URL de la base de datos (opcional)
DATABASE_URL=sqlite:////app/data/traffic_counter.db
```

### Base de Datos

La aplicación utiliza **SQLite** por defecto:
- **Desarrollo local:** `./db/traffic_counter.db`
- **Docker:** `/app/data/traffic_counter.db` (volumen persistente)

El esquema se crea automáticamente al iniciar la aplicación.

## 📁 Estructura del Proyecto

```
mikrotik_management/
├── backend/
│   └── app/
│       ├── api/
│       │   ├── clients.py      # Endpoints de gestión de clientes
│       │   ├── config.py       # Endpoints de configuración
│       │   ├── traffic.py      # Endpoints de datos de tráfico
│       │   ├── views.py        # Endpoints de vistas HTML
│       │   └── demo.py         # Endpoints de demo
│       ├── models.py           # Modelos de base de datos
│       ├── database.py         # Configuración de BD
│       ├── config.py           # Configuración general
│       ├── main.py             # Aplicación principal
│       └── frontend/           # Plantillas Jinja2
├── frontend/
│   ├── static/                 # CSS, JS, iconos
│   └── templates/              # Archivos HTML
│       ├── base.html
│       ├── dashboard.html
│       ├── clients.html
│       ├── address_lists.html
│       ├── config.html
│       ├── login.html
│       └── modals/             # Diálogos modales
├── requirements.txt            # Dependencias Python
├── Dockerfile                  # Configuración Docker
├── docker-compose.yml          # Orquestación Docker
├── main.py                     # Punto de entrada (legacy)
└── README.md                   # Este archivo
```

## 🔌 API Endpoints

### Vistas (HTML)
- `GET /` - Página principal (dashboard)
- `GET /dashboard` - Dashboard con estadísticas
- `GET /clients` - Página de gestión de clientes
- `GET /address-lists` - Listas de direcciones de firewall
- `GET /config` - Página de configuración
- `GET /demo` - Modo demostración

### Clientes
- `GET /api/clients` - Listar clientes con filtros
- `POST /api/clients/add` - Agregar cliente
- `POST /api/clients/bulk-add` - Agregar múltiples clientes
- `PUT /api/clients/{id}` - Editar cliente
- `DELETE /api/clients/{id}` - Eliminar cliente

### Datos de Tráfico
- `GET /api/traffic-data/24h` - Tráfico últimas 24 horas
- `GET /api/traffic-data/7d` - Tráfico últimos 7 días

### Listas de Direcciones
- `GET /api/views/address-lists-summary` - Resumen de listas
- `GET /api/views/address-lists` - Listas con detalles completos

### Configuración
- `GET /api/config` - Obtener configuración actual
- `POST /api/config/update` - Actualizar configuración

## 🐳 Docker Compose

El archivo `docker-compose.yml` incluye:

```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - MK_IP=192.168.1.1
      - MK_USER=api_user
      - MK_PASS=contraseña
      - INTERVALO_MINUTOS=5
    volumes:
      - ./data:/app/data  # Persistencia de BD
    restart: unless-stopped
```

### Comandos útiles

```bash
# Iniciar contenedores
docker-compose up -d

# Ver logs
docker-compose logs -f app

# Detener contenedores
docker-compose down

# Recargar imagen (después de cambios)
docker-compose up -d --build

# Acceder a bash dentro del contenedor
docker-compose exec app bash
```

## 🛠️ Desarrollo Local

### Instalación para desarrollo

```bash
# Crear entorno virtual
python -m venv .venv
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar con auto-reload
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

### Estructura de archivos generada

```
data/
├── traffic_counter.db      # Base de datos SQLite
└── .gitkeep

db/
└── traffic_counter.db      # Primera copia (legacy)
```

## 🔐 Seguridad

### Recomendaciones

1. **Credenciales MikroTik:**
   - Cambiar la contraseña predeterminada
   - Usar un usuario API dedicado con permisos mínimos
   - No compartir las credenciales en repositorios públicos

2. **Variables sensibles:**
   - Nunca verificar `.env` en git
   - Usar secretos de Docker en producción
   - Limitar acceso a puerto 8000

3. **Firewall:**
   - Solo exponer puerto 8000 a usuarios autorizados
   - Usar reverse proxy (nginx) en producción
   - Implementar autenticación si es accesible remotamente

## 🐛 Solución de Problemas

### "Connection refused" al MikroTik

```bash
# Verificar que el MikroTik es accesible
ping 192.168.1.1

# Verificar que API está habilitado
# En MikroTik: /ip service print
```

### Base de datos bloqueada

```bash
# En desarrollo, si hay errores de BD:
rm -f traffic_counter.db
# Reiniciar la aplicación
```

### Gráficos vacíos

- Esperar 5-10 minutos para que se recopilen datos
- Verificar que los datos se envían desde el MikroTik
- Revisar logs: `docker-compose logs app`

### Puerto 8000 en uso

```bash
# Cambiar puerto en docker-compose.yml:
ports:
  - "8080:8000"

# O en desarrollo:
uvicorn backend.app.main:app --host 0.0.0.0 --port 8080
```

## 📊 Datos de Demo

Para probar sin MikroTik real:

```bash
# Generar datos de demostración
python generate_demo.py

# Acceder a /demo en la aplicación
```

## 📝 Logs

### Docker

```bash
# Ver todos los logs
docker-compose logs app

# Últimas 100 líneas
docker-compose logs app --tail=100

# En tiempo real
docker-compose logs -f app
```

### Archivo (desarrollo local)

Los logs se muestran en la consola cuando ejecutas `uvicorn` o `python main.py`.

## 🤝 Contribuir

1. Fork el repositorio
2. Crear rama feature (`git checkout -b feature/algo`)
3. Commit cambios (`git commit -am 'Agregar feature'`)
4. Push a rama (`git push origin feature/algo`)
5. Crear Pull Request

## 📄 Licencia

Especifica tu licencia aquí (MIT, GPL, etc.)

## 📞 Soporte

Para reportar problemas o sugerencias:
- Abrir un issue en el repositorio
- Revisar logs con `docker-compose logs app`
- Verificar credenciales de MikroTik

## 🗺️ Hoja de Ruta

- [ ] Autenticación de usuarios
- [ ] Exportación de reportes (PDF, Excel)
- [ ] Alertas por umbral de consumo
- [ ] Histórico de cambios de configuración
- [ ] API REST completa sin HTML
- [ ] Soporte multi-MikroTik
- [ ] Dark mode
- [ ] Internacionalización (i18n)

---

**Versión:** 1.0.0  
**Última actualización:** Abril 2026  
**Python:** 3.11+  
**FastAPI:** 0.100+
