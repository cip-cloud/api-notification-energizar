# Energizar — API de Recordatorios Comerciales

API que envía recordatorios automáticos diarios desde Odoo 15 Enterprise a cada vendedor con sus actividades pendientes y oportunidades próximas a cierre.

## Stack

- **Python 3.11+** · **FastAPI** · **SQLAlchemy async** · **APScheduler**
- Conexión a Odoo vía **XML-RPC**
- Emails HTML responsivos con **Jinja2**
- **Docker** · **GitHub Container Registry** · **GitHub Actions** para CI/CD

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/api/trigger-reminders` | Ejecutar recordatorios manualmente |
| `GET` | `/api/logs` | Historial de envíos |
| `GET` | `/api/logs/stats` | Estadísticas de envíos |

## Variables de entorno

| Variable | Obligatoria | Descripción |
|---|---|---|
| `ODOO_URL` | Sí | URL de la instancia Odoo |
| `ODOO_DB` | Sí | Base de datos Odoo |
| `ODOO_USER` | Sí | Usuario de conexión |
| `ODOO_PASSWORD` | No* | Contraseña de conexión |
| `ODOO_API_KEY` | No* | API key de Odoo (reemplaza password) |
| `TZ` | No | Zona horaria (default: America/Bogota) |

*Debe especificarse `ODOO_PASSWORD` o `ODOO_API_KEY`. La API key es más segura para conexiones externas. Para generarla: Odoo → Preferencias → Cuenta y Seguridad → Claves de API.
| `DB_URL` | No | URL de BD para logs (default: sqlite) |
| `MS_GRAPH_*` | No | Envío por Graph API y sync de calendario — ver [docs/GRAPH_SETUP.md](docs/GRAPH_SETUP.md) |

## Desarrollo local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # configurar credenciales
uvicorn app.main:app --reload
```

## Despliegue

> Para el despliegue en producción, ver la [lista de requisitos a solicitar a la empresa](docs/DEPLOYMENT_CHECKLIST.md).

El CI/CD está configurado en `.github/workflows/deploy.yml`. Al hacer push a `main`:

1. Build Docker image
2. Push a GHCR
3. SSH al servidor → `docker compose pull && up -d`

### Secrets requeridos en GitHub

| Secret | Descripción |
|---|---|
| `VPS_HOST` | IP o dominio del servidor |
| `VPS_USER` | Usuario SSH |
| `VPS_SSH_KEY` | Llave privada SSH |
| `ODOO_URL` | URL de Odoo |
| `ODOO_DB` | Base de datos Odoo |
| `ODOO_USER` | Usuario Odoo |
| `ODOO_PASSWORD` | Contraseña Odoo (si no usa API key) |
| `ODOO_API_KEY` | API key Odoo (opcional, sobreescribe password) |
| `TZ` | Zona horaria |
| `DB_URL` | URL de BD para logs (default: sqlite) |

### Setup inicial del servidor

```bash
# Una sola vez
mkdir -p /opt/energizar-api
# Copiar docker-compose.yml al servidor
# Configurar variables en .env o en secrets
docker compose up -d
```

## Agentes opencode

El proyecto incluye 4 agentes especializados y 4 skills para desarrollo asistido:

| Agente | Rol |
|---|---|
| `fastapi-builder` | Estructura FastAPI + routers + modelos |
| `odoo-connector` | Cliente XML-RPC + consultas Odoo |
| `email-templater` | Templates Jinja2 + envío de correos |
| `devops-deployer` | Docker + CI/CD |

Usar con: `/opencode <agente> <descripción de la tarea>`
