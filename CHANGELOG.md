# Changelog

Todos los cambios notables en este proyecto serán documentados en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/),
y este proyecto se adhiere a [Semantic Versioning](https://semver.org/es/).

## [Sin Lanzamiento] - Cambios Pendientes

### Planeado
- [ ] Autenticación de usuarios (login/logout)
- [ ] Soporte para múltiples dispositivos MikroTik
- [ ] Exportación de reportes (PDF, Excel)
- [ ] Gráficos comparativos de múltiples clientes
- [ ] Alertas por límites de tráfico
- [ ] Webhook para notificaciones
- [ ] Dark mode
- [ ] API GraphQL como alternativa a REST

---

## [1.0.0] - 2024-01-15

### Agregado
- ✨ **Dashboard Principal**
  - Visualización en tiempo real de clientes activos
  - Gráfico de tráfico de últimas 24 horas con tiempo local
  - Métricas de descarga/subida totales
  - Auto-actualización cada 5 segundos

- ✨ **Gestión de Clientes**
  - Crear, editar y eliminar clientes
  - Eliminación instantánea sin recargar página (HTMX)
  - Tabla interactiva con búsqueda
  - Soporte para comentarios como nombres de cliente

- ✨ **Importación desde MikroTik**
  - Conexión directa a RouterOS API
  - Importación de listas de direcciones (address lists)
  - Vista expandible de todas las IPs en una lista
  - Selección múltiple con checkboxes
  - Preservación automática de comentarios como nombres
  - Fallback a dirección IP si no hay comentario

- ✨ **Monitoreo de Tráfico**
  - Registro automático de tráfico upload/download
  - Gráficos en tiempo real con Chart.js
  - Soporte para zonas horarias locales
  - Muestra todas las 24 horas incluyendo horas con cero tráfico
  - Datos parciales de la hora actual

- ✨ **Modo Demo**
  - Datos de demostración para pruebas sin MikroTik
  - Generación de tráfico simulado
  - Mismas características que modo producción

- ✨ **API REST**
  - 10+ endpoints documentados
  - Retorna datos en JSON y HTML
  - Integración con HTMX para actualizaciones dinámicas
  - Soporte para operaciones CRUD completas

- ✨ **Interfaz de Usuario**
  - Diseño responsivo con TailwindCSS
  - Modales para operaciones complejas
  - Animaciones suaves
  - Formularios validados

- ✨ **Configuración**
  - Variables de entorno para personalización
  - Archivo `.env.example` con valores por defecto
  - Logging estructurado
  - Manejo de errores comprehensive

- ✨ **Documentación**
  - README.md con guía completa
  - DEPLOYMENT.md para producción
  - CONTRIBUTING.md para colaboradores
  - Comentarios en código
  - Docstrings en funciones

- ✨ **Docker**
  - Dockerfile optimizado
  - docker-compose.yml para setup completo
  - Volúmenes para persistencia de datos
  - Variables de entorno configurables

- ✨ **Base de Datos**
  - SQLAlchemy ORM con SQLite
  - Modelos: Host, RegistroTrafico
  - Migración automática de esquema
  - Índices para optimización

### Cambios
- Actualizar a FastAPI 0.100+
- Usar Chart.js 3.9+ para gráficos
- TailwindCSS para styling responsive
- HTMX para actualizaciones sin refresh

### Corregido
- ✅ Gráfico vacío debido a UTC vs tiempo local
- ✅ Comentarios de MikroTik no se preservaban como nombres
- ✅ Clientes no desaparecían al eliminar sin recargar
- ✅ Indentación incorrecta en endpoint de eliminación
- ✅ Tráfico de horas recientes no se mostraba
- ✅ Gráfico no se actualizaba al cambiar de hora

### Eliminado
- Rutas obsoletas de API v0
- Estilos CSS duplicados

---

## [0.9.0] - 2024-01-10

### Agregado
- Versión beta con funcionalidad core
- Conexión básica a MikroTik
- Dashboard simple sin gráficos
- Gestión manual de clientes
- Registro de tráfico en BD

### Cambios
- Refactorizar estructura de carpetas
- Separar rutas de API
- Crear modelos de datos

### Corregido
- Errores de conexión a MikroTik
- Validación de direcciones IP

---

## Guía de Versiones

### Cambios Importantes por Versión

#### 1.0.0 - Lanzamiento Completo
- **Breaking Changes**: Ninguno (primera versión estable)
- **Características Nuevas**: 30+
- **Bugs Corregidos**: 6
- **Migración**: N/A

#### 0.9.0 - Beta
- **Status**: Deprecado
- **Soporte**: Fin de vida

---

## Cómo Reportar Cambios

### Para Usuarios
Si has actualizado y algo no funciona:
1. Consulta la sección **Corregido** de tu versión anterior
2. Lee **Cambios** para nuevas configuraciones necesarias
3. Si persiste, abre un issue en GitHub

### Para Colaboradores
Al crear un PR:
1. Documenta cambios en CHANGELOG.md
2. Sigue el formato Keep a Changelog
3. Actualiza versión en `backend/app/config.py`
4. Incluye sección **Agregado**, **Cambios**, **Corregido** según aplique

---

## Referencias

- [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/)
- [Semantic Versioning](https://semver.org/es/)
- [Guía de Colaboración](CONTRIBUTING.md)

---

## Tabla de Cambios Rápida

| Versión | Fecha | Estado | Notas |
|---------|-------|--------|-------|
| 1.0.0 | 2024-01-15 | ✅ Estable | Lanzamiento completo |
| 0.9.0 | 2024-01-10 | ⚠️ Beta | Deprecado |

---

**Última actualización**: 2024-01-15

Para más detalles técnicos, consulta:
- [README.md](README.md) - Guía de inicio rápido
- [DEPLOYMENT.md](DEPLOYMENT.md) - Guía de producción
- [CONTRIBUTING.md](CONTRIBUTING.md) - Guía de colaboración
