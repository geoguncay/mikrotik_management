# MikroTik Management Dashboard - Makefile
# Comandos útiles para desarrollo y mantenimiento

.PHONY: help install run test lint format clean docker-up docker-down docker-logs
.PHONY: db-reset db-backup db-restore backup logs stop restart

help:
	@echo "MikroTik Management Dashboard - Comandos Útiles"
	@echo ""
	@echo "Instalación y Configuración:"
	@echo "  make install              - Instala dependencias en entorno virtual"
	@echo "  make setup                - Setup completo (entorno + dependencias + .env)"
	@echo ""
	@echo "Desarrollo:"
	@echo "  make run                  - Ejecuta aplicación con reload automático"
	@echo "  make test                 - Ejecuta tests (cuando estén disponibles)"
	@echo "  make lint                 - Valida código con flake8 y pylint"
	@echo "  make format               - Formatea código con black e isort"
	@echo "  make shell                - Abre shell Python interactiva con contexto de app"
	@echo ""
	@echo "Base de Datos:"
	@echo "  make db-reset             - Resetea BD (CUIDADO: borra todos los datos)"
	@echo "  make db-backup            - Crea backup de BD"
	@echo "  make db-restore           - Restaura último backup de BD"
	@echo "  make db-stats             - Muestra estadísticas de BD"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up            - Inicia servicios con docker-compose"
	@echo "  make docker-down          - Detiene servicios"
	@echo "  make docker-logs          - Ver logs en tiempo real"
	@echo "  make docker-shell         - Abre shell en contenedor"
	@echo ""
	@echo "Mantenimiento:"
	@echo "  make backup               - Crea backup de datos y BD"
	@echo "  make logs                 - Ver últimas líneas de logs"
	@echo "  make clean                - Limpia archivos temporales"
	@echo "  make stop                 - Detiene la aplicación"
	@echo "  make restart              - Reinicia la aplicación"
	@echo ""

# ============================================================================
# INSTALACIÓN Y CONFIGURACIÓN
# ============================================================================

install:
	@echo "Instalando dependencias..."
	@test -d .venv || python3 -m venv .venv
	@. .venv/bin/activate && pip install -r requirements.txt
	@echo "✓ Dependencias instaladas"

setup: install
	@echo "Ejecutando setup completo..."
	@bash quick-start.sh

# ============================================================================
# DESARROLLO
# ============================================================================

run:
	@echo "Iniciando aplicación..."
	@. .venv/bin/activate && uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

test:
	@echo "Ejecutando tests..."
	@. .venv/bin/activate && pytest tests/ -v --cov=backend

lint:
	@echo "Validando código..."
	@. .venv/bin/activate && flake8 backend --count --select=E9,F63,F7,F82 --show-source --statistics
	@. .venv/bin/activate && pylint backend/**/*.py --disable=C0111,C0103

format:
	@echo "Formateando código..."
	@. .venv/bin/activate && black backend frontend
	@. .venv/bin/activate && isort backend frontend

shell:
	@echo "Abriendo shell Python..."
	@. .venv/bin/activate && python3

# ============================================================================
# BASE DE DATOS
# ============================================================================

db-reset:
	@echo "⚠️  Reseteando base de datos..."
	@echo "Esto borrará TODOS los datos. ¿Continuar? [y/N]"
	@read -r answer; [ "$$answer" = "y" ] && rm -f data/traffic_counter.db && echo "✓ BD reseteada"

db-backup:
	@echo "Creando backup de BD..."
	@mkdir -p .backups
	@cp data/traffic_counter.db .backups/traffic_counter_$(shell date +%Y%m%d_%H%M%S).db.bak
	@echo "✓ Backup creado en .backups/"

db-restore:
	@echo "Restaurando último backup..."
	@ls -t .backups/*.bak 2>/dev/null | head -1 | xargs -I {} cp {} data/traffic_counter.db
	@echo "✓ BD restaurada"

db-stats:
	@echo "Estadísticas de Base de Datos:"
	@echo "Número de clientes:"
	@sqlite3 data/traffic_counter.db "SELECT COUNT(*) FROM hosts;" || echo "No data"
	@echo "Número de registros de tráfico:"
	@sqlite3 data/traffic_counter.db "SELECT COUNT(*) FROM registro_trafico;" || echo "No data"
	@echo "Tamaño de BD:"
	@ls -lh data/traffic_counter.db | awk '{print $$5}' || echo "N/A"

# ============================================================================
# DOCKER
# ============================================================================

docker-up:
	@echo "Iniciando servicios con docker-compose..."
	@docker-compose up -d
	@echo "✓ Servicios iniciados"
	@echo "Accede a http://localhost:8000"

docker-down:
	@echo "Deteniendo servicios..."
	@docker-compose down
	@echo "✓ Servicios detenidos"

docker-logs:
	@docker-compose logs -f app

docker-shell:
	@docker-compose exec app /bin/bash

# ============================================================================
# MANTENIMIENTO
# ============================================================================

backup: db-backup
	@echo "Creando backup adicional..."
	@mkdir -p .backups
	@tar -czf .backups/backup_$(shell date +%Y%m%d_%H%M%S).tar.gz data/ logs/ 2>/dev/null || true
	@echo "✓ Backup completado"

logs:
	@echo "Últimas líneas de logs:"
	@tail -50 logs/app.log 2>/dev/null || echo "No logs found"

clean:
	@echo "Limpiando archivos temporales..."
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -delete
	@find . -type d -name ".pytest_cache" -delete
	@rm -f .coverage
	@echo "✓ Limpieza completada"

stop:
	@echo "Deteniendo aplicación..."
	@pkill -f "uvicorn backend.app.main" || echo "App no está corriendo"
	@echo "✓ Aplicación detenida"

restart: stop
	@sleep 1
	@echo "Reiniciando aplicación..."
	@make run

# ============================================================================
# UTILIDADES
# ============================================================================

venv.check:
	@test -d .venv || (echo "❌ Entorno virtual no existe"; exit 1)
	@echo "✓ Entorno virtual encontrado"

check: venv.check
	@echo "Verificando setup..."
	@test -f .env || (echo "❌ .env no existe"; exit 1)
	@. .venv/bin/activate && python3 -c "import fastapi; import sqlalchemy" && echo "✓ Dependencias OK"
	@test -f data/traffic_counter.db || echo "⚠️  Base de datos no inicializada (será creada)"
	@echo "✓ Setup verificado"

info:
	@echo "Información del Proyecto:"
	@echo "Python:"
	@python3 --version
	@echo "Dependencias:"
	@. .venv/bin/activate && pip list | grep -E "fastapi|sqlalchemy|uvicorn|chart|htmx" || true
	@echo "Tamaño del Proyecto:"
	@du -sh . 2>/dev/null || echo "N/A"

docs:
	@echo "📚 Documentación disponible:"
	@echo "  - README.md: Guía de inicio"
	@echo "  - DEPLOYMENT.md: Guía de producción"
	@echo "  - CONTRIBUTING.md: Guía de colaboradores"
	@echo "  - TROUBLESHOOTING.md: Resolución de problemas"
	@echo "  - CHANGELOG.md: Historial de cambios"
	@echo ""
	@echo "Abriendo README.md..."
	@test -f README.md && open README.md || echo "README.md no encontrado"

venv.clean:
	@echo "⚠️  Eliminando entorno virtual..."
	@rm -rf .venv
	@echo "✓ Entorno virtual eliminado"

venv.recreate: venv.clean install
	@echo "✓ Entorno virtual recreado"

requirements.update:
	@echo "Actualizando lista de dependencias..."
	@. .venv/bin/activate && pip freeze > requirements.txt
	@echo "✓ requirements.txt actualizado"

# ============================================================================
# PROFILING Y DEBUGGING (Advanced)
# ============================================================================

profile:
	@echo "Profiling de aplicación..."
	@. .venv/bin/activate && python3 -m cProfile -s cumtime backend/app/main.py

trace:
	@echo "Trazando ejecución..."
	@. .venv/bin/activate && python3 -m trace --trace backend/app/main.py

# ============================================================================
# Default target
# ============================================================================

.DEFAULT_GOAL := help
